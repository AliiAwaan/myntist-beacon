#!/usr/bin/env bash
# Secrets Manager bootstrap — Myntist Sovereign Beacon (Criterion B23)
# Creates secret skeletons with placeholder values.
# Real values are rotated in during the first deployment cycle.
# Safe to re-run: uses --no-overwrite-secret-string equivalent logic.
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"

create_or_skip() {
  local name="$1" desc="$2" placeholder="$3"
  if aws secretsmanager describe-secret --secret-id "$name" --region "$REGION" &>/dev/null; then
    echo "  [EXISTS] $name — skipped (already created)"
  else
    aws secretsmanager create-secret \
      --name "$name" \
      --description "$desc" \
      --secret-string "$placeholder" \
      --region "$REGION"
    echo "  [OK] $name"
  fi
}

echo "==> Bootstrapping Secrets Manager secrets in region $REGION ..."

create_or_skip \
  "/myntist/beacon/ed25519-private-key" \
  "Ed25519 signing key for beacon payloads" \
  "placeholder-rotate-after-migration"

create_or_skip \
  "/myntist/beacon/database-url" \
  "RDS connection string" \
  "placeholder-rotate-after-migration"

create_or_skip \
  "/myntist/beacon/hmac-secret" \
  "HMAC webhook signing secret" \
  "placeholder-rotate-after-migration"

echo "==> Listing myntist/beacon secrets ..."
aws secretsmanager list-secrets \
  --region "$REGION" \
  --query "SecretList[?starts_with(Name, '/myntist/beacon/')].{Name:Name,ARN:ARN}" \
  --output table

echo "==> Done."
