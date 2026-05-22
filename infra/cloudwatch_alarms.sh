#!/usr/bin/env bash
# CloudWatch Alarms — Myntist Sovereign Beacon (Criterion B25)
# Run once from any environment with AWS credentials.
# Safe to re-run: put-metric-alarm is idempotent.
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"

echo "==> Creating CloudWatch alarms in region $REGION ..."

# 1. API 5xx error alarm (ALB)
aws cloudwatch put-metric-alarm \
  --alarm-name myntist-beacon-api-5xx \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=LoadBalancer,Value=app/myntist-beacon-alb/288532976 \
  --region "$REGION"
echo "  [OK] myntist-beacon-api-5xx"

# 2. ECS CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name myntist-beacon-cpu-high \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ClusterName,Value=myntist-beacon \
  --region "$REGION"
echo "  [OK] myntist-beacon-cpu-high"

# 3. RDS connection alarm
aws cloudwatch put-metric-alarm \
  --alarm-name myntist-beacon-db-connections \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 15 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=DBInstanceIdentifier,Value=myntist-beacon-db \
  --region "$REGION"
echo "  [OK] myntist-beacon-db-connections"

# 4. Audit log stale alarm (custom metric — optional, skip on missing metric)
aws cloudwatch put-metric-alarm \
  --alarm-name myntist-beacon-audit-stale \
  --metric-name substrate_requests_total \
  --namespace myntist/beacon \
  --statistic Sum \
  --period 900 \
  --threshold 0 \
  --comparison-operator LessThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --region "$REGION" 2>/dev/null && echo "  [OK] myntist-beacon-audit-stale" \
  || echo "  [SKIP] myntist-beacon-audit-stale (custom metric not yet publishing)"

echo "==> Verifying alarms ..."
aws cloudwatch describe-alarms \
  --alarm-names \
    myntist-beacon-api-5xx \
    myntist-beacon-cpu-high \
    myntist-beacon-db-connections \
    myntist-beacon-audit-stale \
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue}" \
  --output table \
  --region "$REGION" 2>/dev/null || true

echo "==> Done."
