#!/usr/bin/env bash
# deploy.sh — Full Myntist Sovereign Beacon deploy pipeline
#
# This script implements the hybrid deployment model documented in DEPLOYMENT.md:
#   1.  Run tests with coverage (≥70% required)
#   2.  Apply S3 bucket policy (role-ARN-scoped CodeBuild + DenyInsecureTransport)
#   3.  Apply DB append-only triggers and VERIFY UPDATE/DELETE are blocked
#   4.  Package and upload source ZIP to S3
#   5.  Trigger CodeBuild project (builds images, pushes to ECR, updates ECS)
#   6.  Wait for CodeBuild SUCCEEDED
#   7.  Wait for ALL ECS services to reach desired count
#   8.  Post-deploy endpoint verification
#
# Usage:
#   cd /path/to/workspace            # repo root containing myntist-fixed/
#   export AWS_ACCESS_KEY_ID=<key>   # or set AWS_API_KEY — script maps it automatically
#   export AWS_SECRET_ACCESS_KEY=<secret>
#   export AWS_DEFAULT_REGION=us-east-1  # optional, defaults to us-east-1
#   bash myntist-fixed/infra/deploy.sh [--skip-tests] [--skip-db] [--dry-run]
#
# Requires: aws-cli v1 or v2, psql, python3, zip

set -euo pipefail

# ── Credential normalisation ─────────────────────────────────────────────────
# Replit injects the access key as AWS_API_KEY; the AWS CLI expects
# AWS_ACCESS_KEY_ID.  Map it if the canonical name is not already set.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_API_KEY:-}" ]; then
  export AWS_ACCESS_KEY_ID="$AWS_API_KEY"
fi
# Propagate region from Replit's AWS_REGION if the CLI var is missing.
if [ -z "${AWS_DEFAULT_REGION:-}" ] && [ -n "${AWS_REGION:-}" ]; then
  export AWS_DEFAULT_REGION="$AWS_REGION"
fi
# Bail early with a clear message if credentials are still incomplete.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "[ERROR] AWS credentials not available."
  echo "        Required env vars: AWS_ACCESS_KEY_ID (or AWS_API_KEY) and AWS_SECRET_ACCESS_KEY"
  echo "        In Replit: open Secrets (padlock icon) and verify both are saved and exported."
  exit 1
fi

REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-225161979546}"
BUCKET="myntist-beacon-src-${ACCOUNT_ID}"
SOURCE_KEY="source/myntist-source.zip"
CODEBUILD_PROJECT="myntist-beacon-build"
# ECS_CLUSTER is exported by Replit config as "myntist-production"
ECS_CLUSTER="${ECS_CLUSTER:-myntist-production}"
# ECS service names are discovered at runtime from the cluster when not overridden.
# Override by setting ECS_SERVICES_OVERRIDE="svc-a svc-b svc-c" before running.
if [ -n "${ECS_SERVICES_OVERRIDE:-}" ]; then
  read -ra ECS_SERVICES <<< "$ECS_SERVICES_OVERRIDE"
else
  ECS_SERVICES=()
fi
# ALB hostname — the CANONICAL_URL config is stale (DNS resolves but host is unreachable).
# Use the verified working hostname; override with ALB_HOST env var if needed.
ALB="${ALB_HOST:-myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com}"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_DIR="$WORKSPACE_ROOT/myntist-fixed"

DRY_RUN=false
SKIP_TESTS=false
SKIP_DB=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --skip-tests) SKIP_TESTS=true ;;
    --skip-db)    SKIP_DB=true ;;
  esac
done

info()  { echo "[INFO]  $(date -u +%H:%M:%SZ)  $*"; }
warn()  { echo "[WARN]  $(date -u +%H:%M:%SZ)  $*"; }
error() { echo "[ERROR] $(date -u +%H:%M:%SZ)  $*" >&2; exit 1; }

info "=== Myntist Sovereign Beacon Deploy ==="
info "Region: $REGION | Account: $ACCOUNT_ID | Dry-run: $DRY_RUN"
info "Workspace: $WORKSPACE_ROOT"

# ── Step 1: Run tests with coverage ─────────────────────────────────────────
if [ "$SKIP_TESTS" = "false" ]; then
  info ""
  info "--- Step 1: Running test suite (minimum 70% coverage) ---"
  cd "$SRC_DIR/myntist-beacon"
  python3 -m pytest tests/ \
    --cov=beacon_core --cov=iam_substrate --cov=kcp --cov=identity_loop \
    --cov-report=term-missing \
    --cov-fail-under=70 \
    -q --tb=short
  info "Tests PASSED with ≥70% coverage."
  cd "$WORKSPACE_ROOT"
else
  warn "--- Step 1: Tests SKIPPED (--skip-tests) ---"
fi

# ── Step 2: Apply S3 bucket policy ──────────────────────────────────────────
info ""
info "--- Step 2: Applying S3 bucket policy ---"
POLICY_FILE="$SRC_DIR/infra/s3_bucket_policy.json"
# Strip JSON-comment-only fields before sending to AWS CLI
CLEAN_POLICY=$(python3 -c "
import json
p = json.load(open('$POLICY_FILE'))
for k in list(p.keys()):
    if k.startswith('_'):
        del p[k]
print(json.dumps(p))
")
if [ "$DRY_RUN" = "false" ]; then
  aws s3api put-bucket-policy \
    --bucket "$BUCKET" \
    --policy "$CLEAN_POLICY" \
    --region "$REGION"
  # Verify the policy was accepted
  aws s3api get-bucket-policy \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --query Policy --output text | python3 -m json.tool | grep '"Sid"' | sort
  info "S3 bucket policy applied and verified."
else
  warn "[DRY-RUN] Would apply role-ARN-scoped bucket policy to $BUCKET"
fi

# ── Step 3: Apply DB append-only triggers and verify ────────────────────────
if [ "$SKIP_DB" = "false" ]; then
  info ""
  info "--- Step 3: Applying + verifying DB append-only triggers ---"
  if [ -z "${DATABASE_URL:-}" ]; then
    info "Fetching DATABASE_URL from SSM..."
    DATABASE_URL=$(aws ssm get-parameter \
      --name /myntist/beacon/DATABASE_URL \
      --with-decryption \
      --query Parameter.Value \
      --output text \
      --region "$REGION")
    export DATABASE_URL
  fi

  if [ "$DRY_RUN" = "false" ]; then
    # Apply migration (idempotent: uses CREATE OR REPLACE / IF NOT EXISTS)
    info "Applying 001_audit_log_append_only.sql ..."
    psql "$DATABASE_URL" -f "$SRC_DIR/myntist-beacon/infra/sql/001_audit_log_append_only.sql"

    # Verify trigger count
    TRIGGER_COUNT=$(psql "$DATABASE_URL" -tAc \
      "SELECT count(*) FROM pg_trigger WHERE tgrelid='iam_substrate_log'::regclass AND tgname IN ('trg_audit_no_update','trg_audit_no_delete');")
    if [ "${TRIGGER_COUNT:-0}" -lt 2 ]; then
      error "Expected 2 triggers (trg_audit_no_update + trg_audit_no_delete), found ${TRIGGER_COUNT:-0}"
    fi
    info "Trigger count verified: $TRIGGER_COUNT/2 triggers present."

    # Verify INSERT still works (append-only means inserts must succeed)
    info "Verifying INSERT is allowed ..."
    TEST_ID=$(psql "$DATABASE_URL" -tAc \
      "INSERT INTO iam_substrate_log (identity_id, event_type, action)
       VALUES ('_deploy_test', 'deploy_verify', 'append-only-check')
       RETURNING id;" 2>&1 || echo "INSERT_FAILED")
    if echo "$TEST_ID" | grep -q "INSERT_FAILED\|ERROR"; then
      error "INSERT test row failed — append-only invariant broken or table schema mismatch. Aborting deploy."
    fi
    info "INSERT succeeded (row id=$TEST_ID)."

    # Verify UPDATE is blocked — HARD GATE: deploy must fail if UPDATE succeeds
    info "Verifying UPDATE is blocked ..."
    UPDATE_OUT=$(psql "$DATABASE_URL" -c \
      "UPDATE iam_substrate_log SET action='tamper_attempt' WHERE id='$TEST_ID';" \
      2>&1 || true)
    if echo "$UPDATE_OUT" | grep -qi "append-only\|not permitted\|ERROR"; then
      info "UPDATE correctly blocked by trigger: ${UPDATE_OUT:0:120}"
    else
      error "UPDATE trigger NOT active — response: ${UPDATE_OUT:0:200}. Audit log integrity is compromised. Aborting deploy."
    fi

    # Verify DELETE is blocked — HARD GATE: deploy must fail if DELETE succeeds
    info "Verifying DELETE is blocked ..."
    DELETE_OUT=$(psql "$DATABASE_URL" -c \
      "DELETE FROM iam_substrate_log WHERE id='$TEST_ID';" \
      2>&1 || true)
    if echo "$DELETE_OUT" | grep -qi "append-only\|not permitted\|ERROR"; then
      info "DELETE correctly blocked by trigger: ${DELETE_OUT:0:120}"
    else
      error "DELETE trigger NOT active — response: ${DELETE_OUT:0:200}. Audit log integrity is compromised. Aborting deploy."
    fi
  else
    warn "[DRY-RUN] Would apply 001_audit_log_append_only.sql and verify INSERT/UPDATE/DELETE"
  fi
else
  warn "--- Step 3: DB triggers SKIPPED (--skip-db) ---"
fi

# ── Step 4: Package and upload source ZIP ────────────────────────────────────
info ""
info "--- Step 4: Packaging source ZIP ---"
TMP_ZIP="/tmp/myntist-source-$(date +%Y%m%d%H%M%S).zip"
cd "$WORKSPACE_ROOT"
zip -r "$TMP_ZIP" myntist-fixed/ \
  -x "*.pyc" \
  -x "*/__pycache__/*" \
  -x "*.egg-info/*" \
  -x ".git/*" \
  -x "node_modules/*" \
  -x "*/node_modules/*" \
  -x ".pythonlibs/*" \
  -x "*.log" \
  > /dev/null
info "Source ZIP created: $TMP_ZIP ($(du -sh "$TMP_ZIP" | cut -f1))"

if [ "$DRY_RUN" = "false" ]; then
  aws s3 cp "$TMP_ZIP" "s3://$BUCKET/$SOURCE_KEY" \
    --region "$REGION" \
    --sse aws:kms
  # Verify the object exists and is non-zero
  OBJ_SIZE=$(aws s3api head-object \
    --bucket "$BUCKET" --key "$SOURCE_KEY" \
    --region "$REGION" \
    --query ContentLength --output text 2>/dev/null || echo "0")
  info "Uploaded: s3://$BUCKET/$SOURCE_KEY (${OBJ_SIZE} bytes)"
  rm -f "$TMP_ZIP"
else
  warn "[DRY-RUN] Would upload $TMP_ZIP to s3://$BUCKET/$SOURCE_KEY"
  rm -f "$TMP_ZIP"
fi

# ── Step 5: Trigger CodeBuild ────────────────────────────────────────────────
info ""
info "--- Step 5: Triggering CodeBuild project: $CODEBUILD_PROJECT ---"
if [ "$DRY_RUN" = "false" ]; then
  BUILD_ID=$(aws codebuild start-build \
    --project-name "$CODEBUILD_PROJECT" \
    --region "$REGION" \
    --query 'build.id' --output text)
  info "Build started: $BUILD_ID"
  info "Console: https://$REGION.console.aws.amazon.com/codesuite/codebuild/$ACCOUNT_ID/projects/$CODEBUILD_PROJECT/build/$BUILD_ID/?region=$REGION"

  # ── Step 6: Wait for build completion ───────────────────────────────────
  info ""
  info "--- Step 6: Polling CodeBuild until SUCCEEDED (max 30 min) ---"
  BUILD_SUCCEEDED=false
  for i in $(seq 1 60); do
    sleep 30
    STATUS=$(aws codebuild batch-get-builds \
      --ids "$BUILD_ID" \
      --region "$REGION" \
      --query 'builds[0].buildStatus' --output text)
    info "  [poll ${i}/60] Build status: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ]; then
      BUILD_SUCCEEDED=true
      break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ] || [ "$STATUS" = "TIMED_OUT" ]; then
      # Print last 20 lines of build log for quick diagnosis
      LOG_GROUP=$(aws codebuild batch-get-builds \
        --ids "$BUILD_ID" --region "$REGION" \
        --query 'builds[0].logs.groupName' --output text 2>/dev/null || echo "")
      LOG_STREAM=$(aws codebuild batch-get-builds \
        --ids "$BUILD_ID" --region "$REGION" \
        --query 'builds[0].logs.streamName' --output text 2>/dev/null || echo "")
      if [ -n "$LOG_GROUP" ] && [ -n "$LOG_STREAM" ]; then
        warn "Last log lines from $LOG_GROUP/$LOG_STREAM:"
        aws logs get-log-events \
          --log-group-name "$LOG_GROUP" \
          --log-stream-name "$LOG_STREAM" \
          --limit 20 --region "$REGION" \
          --query 'events[*].message' --output text 2>/dev/null | tail -20 || true
      fi
      error "Build $STATUS — check CodeBuild console."
    fi
  done
  if [ "$BUILD_SUCCEEDED" = "false" ]; then
    error "Build did not complete within 30 minutes."
  fi
else
  warn "[DRY-RUN] Would trigger $CODEBUILD_PROJECT and wait for SUCCEEDED"
fi

# ── Step 7: Verify ALL ECS services reach their desired count ────────────────
info ""
info "--- Step 7: Waiting for ECS services to reach desired count ---"
if [ "$DRY_RUN" = "false" ]; then
  # Auto-discover services from the cluster if none were explicitly provided.
  if [ "${#ECS_SERVICES[@]}" -eq 0 ]; then
    info "  Auto-discovering ECS services in cluster: $ECS_CLUSTER"
    mapfile -t ECS_SERVICES < <(
      aws ecs list-services \
        --cluster "$ECS_CLUSTER" \
        --region "$REGION" \
        --query 'serviceArns[*]' \
        --output text 2>/dev/null \
      | tr '\t' '\n' \
      | xargs -I{} basename {}
    )
    if [ "${#ECS_SERVICES[@]}" -eq 0 ]; then
      warn "  No ECS services found in cluster $ECS_CLUSTER — skipping service health check."
    else
      info "  Discovered ${#ECS_SERVICES[@]} service(s): ${ECS_SERVICES[*]}"
    fi
  fi
  ALL_HEALTHY=true
  for SVC in "${ECS_SERVICES[@]}"; do
    info "  Checking service: $SVC"
    SVC_HEALTHY=false
    for i in $(seq 1 20); do
      sleep 15
      RUNNING=$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" --services "$SVC" --region "$REGION" \
        --query 'services[0].runningCount' --output text 2>/dev/null || echo "0")
      DESIRED=$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" --services "$SVC" --region "$REGION" \
        --query 'services[0].desiredCount' --output text 2>/dev/null || echo "0")
      STATUS=$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" --services "$SVC" --region "$REGION" \
        --query 'services[0].status' --output text 2>/dev/null || echo "UNKNOWN")
      TASK_DEF=$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" --services "$SVC" --region "$REGION" \
        --query 'services[0].taskDefinition' --output text 2>/dev/null || echo "")
      info "  [${SVC}] poll ${i}/20: status=$STATUS running=$RUNNING desired=$DESIRED taskDef=$(basename "${TASK_DEF:-unknown}")"
      if [ "${RUNNING:-0}" -ge "${DESIRED:-1}" ] && [ "${DESIRED:-0}" -gt 0 ]; then
        info "  [${SVC}] HEALTHY — $RUNNING/$DESIRED tasks running."
        SVC_HEALTHY=true
        break
      fi
    done
    if [ "$SVC_HEALTHY" = "false" ]; then
      error "  [${SVC}] did not reach desired count within 5 minutes. Aborting — check ECS console for stopped task reason."
    fi
  done
  if [ "$ALL_HEALTHY" = "false" ]; then
    error "One or more ECS services did not reach desired state — deploy aborted."
  else
    info "All ECS services healthy."
  fi
else
  warn "[DRY-RUN] Would check ECS services: ${ECS_SERVICES[*]}"
fi

# ── Step 8: Post-deploy endpoint verification ─────────────────────────────────
info ""
info "--- Step 8: Post-deploy endpoint verification ---"

ENDPOINT_FAILURES=0

_verify() {
  local label="$1"
  local url="$2"
  local check="${3:-}"
  local http_code
  http_code=$(curl -sfo /tmp/_myntist_verify.json -w "%{http_code}" --max-time 15 "$url" 2>/dev/null || echo "000")

  if [ "$http_code" = "000" ]; then
    warn "  [FAIL] $label — $url unreachable (curl 000). ALB may still be initialising."
    ENDPOINT_FAILURES=$((ENDPOINT_FAILURES + 1))
    return 1
  fi

  if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
    warn "  [FAIL] $label — HTTP $http_code from $url"
    ENDPOINT_FAILURES=$((ENDPOINT_FAILURES + 1))
    return 1
  fi

  if [ -n "$check" ]; then
    ASSERTION_OK=$(python3 -c "
import sys, json
try:
    d = json.loads(open('/tmp/_myntist_verify.json').read() or '{}')
except Exception:
    d = {}
ok = bool($check)
print('1' if ok else '0')
" 2>/dev/null || echo "0")
    if [ "$ASSERTION_OK" = "1" ]; then
      info "  [PASS] $label — HTTP $http_code, assertion OK"
    else
      PAYLOAD=$(python3 -c "import json; print(json.dumps(json.load(open('/tmp/_myntist_verify.json')))[:300])" 2>/dev/null || echo "(unreadable)")
      warn "  [FAIL] $label — assertion ($check) failed. payload: $PAYLOAD"
      ENDPOINT_FAILURES=$((ENDPOINT_FAILURES + 1))
      return 1
    fi
  else
    info "  [PASS] $label — HTTP $http_code"
  fi
}

BASE="http://$ALB"
_verify "GET /api/health"               "$BASE/api/health"               "d.get('status')=='ok'"
_verify "GET /api/field/v1/status.json" "$BASE/api/field/v1/status.json" "'@context' in d and '@type' in d"
_verify "GET /api/telemetry/latest"     "$BASE/api/telemetry/latest"     "True"
_verify "GET /api/telemetry/finance"    "$BASE/api/telemetry/finance"    "True"

if [ "$ENDPOINT_FAILURES" -gt 0 ]; then
  error "$ENDPOINT_FAILURES post-deploy endpoint check(s) FAILED — deploy aborted. Review ALB/ECS logs."
fi
info "All $((4 - ENDPOINT_FAILURES)) endpoint checks passed."

# Verify DB triggers still live post-deploy
if [ "$SKIP_DB" = "false" ] && [ -n "${DATABASE_URL:-}" ] && [ "$DRY_RUN" = "false" ]; then
  info ""
  info "--- Post-deploy DB trigger re-verification ---"
  TC=$(psql "$DATABASE_URL" -tAc \
    "SELECT count(*) FROM pg_trigger WHERE tgrelid='iam_substrate_log'::regclass AND tgname IN ('trg_audit_no_update','trg_audit_no_delete');" 2>/dev/null || echo "0")
  if [ "${TC:-0}" -ge 2 ]; then
    info "  DB triggers intact post-deploy: $TC/2"
  else
    error "  DB triggers missing post-deploy ($TC/2) — CodeBuild may have re-run a migration that dropped them. Manually re-apply infra/sql/001_audit_log_append_only.sql and investigate. Marking deploy FAILED."
  fi
fi

info ""
info "=== Deploy pipeline COMPLETE === $(date -u)"
