# Lens Protocol EC2 Investigation — 54.234.168.96

**Date**: 2026-05-07
**Target IP**: 54.234.168.96 (us-east-1 public address)
**Investigator**: Automated — Myntist Sovereign Beacon Task #2

---

## Status: SSH Access Not Available From Replit Environment

The Replit workspace does not have an SSH private key provisioned for the
target EC2 instance and does not have outbound SSH (port 22) access to
public AWS EC2 addresses. Direct shell investigation was not possible.

---

## Network Probe Results

```bash
# Attempted from Replit workspace:
# nc -zvw5 54.234.168.96 22   → connection refused or timed out
# nc -zvw5 54.234.168.96 80   → not checked (no known service on 80)
# nc -zvw5 54.234.168.96 3000 → not checked (Lens Protocol default)
```

Replit sandboxes have restricted outbound network access; most port-scan and
SSH-probe results are unreliable from this environment.

---

## Manual Investigation Procedure

An operator with the appropriate EC2 key pair should run the following to
check the Lens Protocol poster process:

```bash
# 1. Identify the key pair name associated with the instance
aws ec2 describe-instances \
  --filters "Name=ip-address,Values=54.234.168.96" \
  --query "Reservations[*].Instances[*].{Id:InstanceId,State:State.Name,KeyName:KeyName,Type:InstanceType}" \
  --region us-east-1 \
  --output table

# 2. SSH to the instance (replace <key.pem> with actual key)
ssh -i ~/.ssh/<key.pem> ubuntu@54.234.168.96

# 3. Check whether the Lens Protocol poster process is running
sudo systemctl status lens-poster 2>/dev/null || \
  ps aux | grep -i lens | grep -v grep

# 4. Check process ports
sudo ss -tlnp | grep -E "3000|4000|8080"

# 5. Check last 100 log lines if service exists
sudo journalctl -u lens-poster --no-pager -n 100

# 6. Check if process auto-restarts are enabled
sudo systemctl is-enabled lens-poster 2>/dev/null || echo "service not registered"
```

---

## Known Context

- **IP**: 54.234.168.96 is a public Elastic IP in us-east-1 in account 225161979546.
- **Purpose**: This instance runs the Lens Protocol poster, which publishes
  Myntist field state data to the Lens social graph protocol.
- **Expected process name**: `lens-poster` or a Node.js/Python process reading
  `status.json` from the beacon's S3 bucket and posting to the Lens API.

---

## Findings

| Check | Expected | Finding |
|---|---|---|
| Instance reachable on SSH (port 22) | Yes | ⚠️ Not verified (no key pair in workspace) |
| `lens-poster` process running | Yes | ⚠️ Not verified |
| Process enabled on startup | Yes | ⚠️ Not verified |
| Recent activity in logs | Yes (last 24 h) | ⚠️ Not verified |
| Lens API calls succeeding | Yes | ⚠️ Not verified |

---

## Recommendations

1. **Ensure systemd unit is enabled**: `sudo systemctl enable lens-poster` if it
   is not already. This prevents the poster going dark after an instance reboot.

2. **Add CloudWatch metric alarm**: Set an alarm on the `AWS/EC2` `StatusCheckFailed`
   metric for instance `54.234.168.96` so the on-call team is notified if the
   instance goes into an unhealthy state.

3. **Migrate to ECS or Lambda**: Running the Lens poster on a standalone EC2 instance
   is operationally heavier than a containerised ECS task or a scheduled Lambda.
   Migrating to a Lambda on a 5-minute EventBridge schedule would eliminate the
   need to maintain an EC2 instance entirely.

4. **Store Lens API credentials in SSM**: If the poster uses a Lens protocol API key,
   confirm it is stored in SSM Parameter Store at `/myntist/beacon/LENS_API_KEY`
   rather than hardcoded in the instance user data.

---

## Gap Documentation

This investigation is **INCOMPLETE** due to missing SSH access. To close this item:
- Provide the EC2 key pair `.pem` file in SSM at `/myntist/beacon/EC2_SSH_KEY`
- Or grant the IAM user `ssm:StartSession` permission on the instance so AWS Systems
  Manager Session Manager can be used instead of SSH:
  `aws ssm start-session --target <INSTANCE_ID> --region us-east-1`
