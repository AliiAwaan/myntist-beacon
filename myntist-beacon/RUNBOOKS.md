# Myntist Sovereign Beacon — Runbooks

Operational runbooks for the Beacon ECS service (cluster: `myntist-beacon`,
account: 225161979546, region: us-east-1).

---

## 1. Service Health Check

```bash
curl -s http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/health | jq .
```

Expected: `{ "status": "ok", "version": "2.0.0", "timestamp": "..." }`

---

## 2. View Live Logs

```bash
aws logs tail /ecs/myntist-beacon --follow --region us-east-1
```

Filter for errors:

```bash
aws logs filter-log-events \
  --log-group-name /ecs/myntist-beacon \
  --filter-pattern "ERROR" \
  --region us-east-1
```

---

## 3. Deploy a New Image

```bash
# 1. Re-zip source from workspace
cd /home/runner/workspace
zip -r /tmp/myntist-source.zip myntist-fixed/ -x "*.pyc" -x "*/__pycache__/*"

# 2. Upload to S3
aws s3 cp /tmp/myntist-source.zip \
  s3://myntist-beacon-src-225161979546/source/myntist-source.zip

# 3. Trigger CodeBuild
aws codebuild start-build \
  --project-name myntist-beacon-build \
  --region us-east-1

# 4. After build completes, register new task def and update service
# (see deploy.sh in infra/)
```

---

## 4. Rollback ECS Service

```bash
# List task definition revisions
aws ecs list-task-definitions --family-prefix myntist-beacon-task --region us-east-1

# Update service to a prior revision (e.g. rev21)
aws ecs update-service \
  --cluster myntist-beacon \
  --service myntist-beacon-api \
  --task-definition myntist-beacon-task:21 \
  --region us-east-1
```

---

## 5. Database Access (Read-Only Diagnostic)

```bash
# Get DATABASE_URL from SSM
DB_URL=$(aws ssm get-parameter \
  --name /myntist/beacon/DATABASE_URL \
  --with-decryption --query 'Parameter.Value' --output text)

psql "$DB_URL" -c "SELECT COUNT(*) FROM audit_log;"
psql "$DB_URL" -c "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 10;"
```

---

## 6. Force Telemetry Flush

```bash
# POST a score event to trigger an immediate telemetry row
curl -s -X POST http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/score \
  -H 'Content-Type: application/json' \
  -d '{"identity_id":"runbook-test","Q":1.0,"nabla_phi":0.0,"tau":1.0}' | jq .
```

---

## 7. Audit Log Verification

```bash
DB_URL=$(aws ssm get-parameter \
  --name /myntist/beacon/DATABASE_URL \
  --with-decryption --query 'Parameter.Value' --output text)

# Check row count (should increase over time, never decrease)
psql "$DB_URL" -c "SELECT COUNT(*) FROM audit_log;"

# Confirm append-only trigger is installed
psql "$DB_URL" -c "SELECT tgname FROM pg_trigger WHERE tgname='trg_audit_log_no_update_delete';"
```

---

## 8. Policy Engine Status

```bash
# View active policies (admin key required)
curl -s http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/policy/active | jq .

# Evaluate a scenario
curl -s -X POST \
  http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/policy/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"S":0.5,"delta_S":-0.1,"Q":0.8,"tau":0.9,"D":0.05,"Ttau":0.3}' | jq .
```

---

## 9. Ed25519 Signature Verification

```bash
# Fetch status payload
STATUS=$(curl -s http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/field/v1/status.json)
SIG=$(echo $STATUS | jq -r '.signature')

# Verify
curl -s -X POST \
  http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/field/v1/verify \
  -H 'Content-Type: application/json' \
  -d "{\"payload\": $STATUS, \"signature\": \"$SIG\"}" | jq .
```

---

## 10. DNS Anchoring Check

```bash
# Check TXT records on myntist.com
dig TXT _s.v1.myntist.com +short
dig TXT _buoy.latest.myntist.com +short
dig TXT _float.audit.myntist.com +short
dig TXT _ledger.anchor.myntist.com +short
```

---

## 11. CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| `myntist-beacon-5xx` | >5 errors/min | Page on-call |
| `myntist-beacon-cpu` | >80% 5m avg | Scale out |
| `myntist-beacon-mem` | >85% | Investigate memory leak |
| `myntist-beacon-audit-gap` | 0 audit rows in 5 min | Page on-call |

To view alarm state:
```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix myntist-beacon \
  --region us-east-1 \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}'
```

---

## 12. Scaling

```bash
# Scale desired count
aws ecs update-service \
  --cluster myntist-beacon \
  --service myntist-beacon-api \
  --desired-count 2 \
  --region us-east-1
```

Autoscaling is not currently enabled. Scale manually during peak events then return to 1.

---

## 13. Incident Response

### Severity Levels

| Level | Definition | Response Time |
|-------|-----------|---------------|
| P0 | Service down / no audit rows / data loss | 15 min |
| P1 | >1% of requests returning 5xx | 1 hour |
| P2 | Performance degradation or non-critical feature failure | 4 hours |
| P3 | Minor UI issue or warning in logs | Next business day |

### P0 Response Steps

1. **Confirm the incident**
   ```bash
   curl -sf http://myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com/api/health
   ```
   If this returns a non-200, the service is down.

2. **Check ECS task status**
   ```bash
   aws ecs describe-services \
     --cluster myntist-beacon \
     --services myntist-beacon-api \
     --region us-east-1 \
     --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
   ```

3. **Check recent logs for crash cause**
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/myntist-beacon \
     --filter-pattern "ERROR CRITICAL Traceback" \
     --start-time $(($(date +%s) - 900))000 \
     --region us-east-1
   ```

4. **If container is crash-looping — rollback**
   ```bash
   # Identify last stable revision from deploy history
   aws ecs list-task-definitions \
     --family-prefix myntist-beacon-task \
     --sort DESC \
     --region us-east-1 \
     --query 'taskDefinitionArns[:5]'

   # Rollback to prior revision
   aws ecs update-service \
     --cluster myntist-beacon \
     --service myntist-beacon-api \
     --task-definition myntist-beacon-task:<STABLE_REV> \
     --region us-east-1
   ```

5. **If database is unreachable**
   ```bash
   # Check RDS instance status
   aws rds describe-db-instances \
     --db-instance-identifier myntist-beacon-db \
     --region us-east-1 \
     --query 'DBInstances[0].DBInstanceStatus'

   # If stopped, start it
   aws rds start-db-instance \
     --db-instance-identifier myntist-beacon-db \
     --region us-east-1
   ```

6. **If audit log gap detected**
   - Confirm the `live_telemetry` APScheduler job is running (check logs for
     `"Live telemetry emitter started"` message on startup).
   - Force a manual score POST (see Section 6) to verify the DB write path.
   - Check `audit_log` row count before and after.

7. **Notify stakeholders**
   - Post to `#myntist-beacon-alerts` Slack channel with:
     - Incident start time
     - Symptom description
     - Current action being taken
     - ETA for resolution

8. **Post-mortem** — within 48 hours of incident close, file a post-mortem document
   covering: timeline, root cause, fix, and prevention measures.

### Contacts

| Role | Contact |
|------|---------|
| SRE on-call | See PagerDuty rotation |
| Geoff (Trust owner) | Broomhead Private Sovereign Trust |
| AWS Account | 225161979546 (us-east-1) |
