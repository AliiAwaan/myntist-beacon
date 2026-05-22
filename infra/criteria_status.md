# Myntist Sovereign Beacon — Criteria Status

**Date**: 2026-05-07

This document tracks criteria that are either BLOCKED on external dependencies or
confirmed LIVE. Update as blockers are resolved.

---

## LIVE — Implemented and Verifiable

| Criterion | Endpoint / Evidence |
|---|---|
| B46 — RSS 2.0 feed | `GET /api/rss.xml` → `application/rss+xml` with recent pulses |
| Health check | `GET /api/health` → `{"status":"ok"}` |
| Field status JSON-LD | `GET /api/field/v1/status.json` → `@context` + `@type` present |
| Temporal IAM gate | `GET /api/telemetry/temporal` → tau, Q, Ttau, D, admitted |
| Policy engine | `GET /api/policy/active`, `POST /api/policy/evaluate` |
| Prometheus metrics | `GET /api/metrics` → Prometheus plaintext |

---

## BLOCKED — Slack Webhook (Criterion: Slack notifications)

**Status**: BLOCKED pending client action.

**Reason**: A Slack incoming webhook URL must be created by the workspace
administrator and provided to the engineering team. The notification logic
is implemented but the `SLACK_WEBHOOK_URL` environment variable is unset.

**Resolution**: Client provides webhook URL → set it as SSM parameter
`/myntist/beacon/SLACK_WEBHOOK_URL` → redeploy ECS task definition.

---

## BLOCKED — TLS / HTTPS on ALB (Criterion #82)

**Status**: BLOCKED pending custom domain delegation.

**Reason**: AWS Certificate Manager (ACM) cannot issue certificates for raw
ELB hostnames (e.g. `*.us-east-1.elb.amazonaws.com`). A certificate can only
be issued for a domain the requester controls — specifically a subdomain of
`myntist.com` (e.g. `beacon.myntist.com`).

The GoDaddy DNS management credentials (`GODADDY_API_KEY` / `GODADDY_API_SECRET`)
are stored in SSM but the actual DNS delegation step (adding a CNAME or A record
pointing `beacon.myntist.com` → the ALB) cannot be completed without either:
- Operator access to the GoDaddy control panel, **or**
- The `godaddy_updater.py` script being run with valid API credentials that
  have write permission to the `myntist.com` zone.

**Resolution path**:
1. Verify GoDaddy API key has write access to `myntist.com`.
2. Add CNAME: `beacon.myntist.com` → `myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com`
3. Request ACM cert: `aws acm request-certificate --domain-name beacon.myntist.com --validation-method DNS`
4. Add DNS validation CNAME from ACM to GoDaddy zone.
5. Once cert is issued: `aws elbv2 create-listener --protocol HTTPS --port 443 ...`

---

## BLOCKED — CloudWatch Alarms (Criterion B25)

**Status**: Script ready; BLOCKED on `AWS_SECRET_ACCESS_KEY` not injected into environment.

**Reason**: The `AWS_API_KEY` and `AWS_ACCOUNT_ID` env vars are present but
`AWS_SECRET_ACCESS_KEY` is not set, so `aws cloudwatch put-metric-alarm` fails
with "Partial credentials found in env, missing: AWS_SECRET_ACCESS_KEY".

**What's ready**: `infra/cloudwatch_alarms.sh` — idempotent script that creates
four alarms (ALB 5xx, ECS CPU, RDS connections, audit-stale custom metric).
Run with a properly credentialled shell or from ECS task role.

**Resolution**: Ensure `AWS_SECRET_ACCESS_KEY` is available and run:
```
AWS_ACCESS_KEY_ID=$AWS_API_KEY bash infra/cloudwatch_alarms.sh
```

---

## BLOCKED — Secrets Manager Bootstrap (Criterion B23)

**Status**: Script ready; BLOCKED on same missing `AWS_SECRET_ACCESS_KEY`.

**What's ready**: `infra/create_secrets.sh` — idempotent script that creates
three secret skeletons with placeholder values:
- `/myntist/beacon/ed25519-private-key`
- `/myntist/beacon/database-url`
- `/myntist/beacon/hmac-secret`

Real values rotated in during the first deployment cycle.

**Resolution**: Run `bash infra/create_secrets.sh` from a credentialled shell.

---

## BLOCKED — GitHub Actions CI Trigger (Criteria #9, #45, #68)

**Status**: BLOCKED on repo admin access to `g-broomhead-trust/myntist-iam-substrate`.

**Reason**: Repository secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_ACCOUNT_ID`, `DATABASE_URL`, `ED25519_PRIVATE_KEY_HEX`) must be configured
by the repo owner under Settings → Secrets and variables → Actions before
`deploy.yml` can complete a successful run.

**Resolution**: Repo owner adds the five secrets listed above, then pushes any
commit to `main` to trigger the deployment workflow.

---

## BLOCKED — KMS Key Policy Audit (trust-ledger-kms-key-01)

**Status**: BLOCKED — KMS API calls cannot be made from outside the ECS task boundary
with the stored credentials. See `infra/kms_policy_audit.md` for the manual retrieval
procedure and expected policy.

---

## BLOCKED — Lens Protocol EC2 Verification (54.234.168.96)

**Status**: BLOCKED — SSH key pair not provisioned in this environment.
See `infra/lens_protocol_status.md` for manual investigation procedure.
