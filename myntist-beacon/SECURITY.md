# Security Policy — Myntist Sovereign Beacon

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email `security@myntist.com` with subject `[SECURITY] Myntist Beacon — <description>`.
Expect acknowledgement within 48 hours. Critical issues resolved within 14 days.
We follow a 90-day coordinated disclosure timeline.

---

## 1. HMAC Webhook Authentication

All requests to `POST /events` must carry a valid HMAC-SHA-256 signature.

- **Header**: `X-Signature: sha256=<hex-digest>`
- **Secret**: `SUBSTRATE_HMAC_SECRET` — stored in SSM at `/myntist/beacon/SUBSTRATE_HMAC_SECRET`
- **Verification**: `webhooks/hmac_handler.py::require_valid_signature` — rejects with HTTP 401 when
  the header is absent, HTTP 403 when the digest is wrong.
- Rotate the secret quarterly; see ROTATION_POLICY.md §HMAC Rotation.

---

## 2. Ed25519 Signing

Every `status.json` payload is signed with an Ed25519 private key.

- **Algorithm**: Ed25519 (RFC 8032) — 32-byte private key, hex-encoded.
- **Key material**: `ED25519_PRIVATE_KEY_HEX` in SSM at `/myntist/beacon/ED25519_PRIVATE_KEY_HEX`.
- **Public key endpoint**: `GET /.well-known/field-signing-keys.json` (W3C Ed25519VerificationKey2020 doc).
- **Signature field**: `status.json` carries `"signature": "ed25519:<base64>"`.
- **Verification endpoint**: `POST /field/v1/verify` accepts `{ payload, signature }` and returns `{ valid: true/false }`.
- **Canonical bytes**: JSON of all payload fields except `hash` and `signature`, serialised with `sort_keys=True`.
- Rotate annually; see ROTATION_POLICY.md §Ed25519 Rotation.

---

## 3. KMS Integration

AWS KMS (RSA-PSS SHA-256) is supported as an alternative signing backend.

- **Key identifier**: `KMS_KEY_ID` — must be a full ARN, not an alias.
- **Algorithm**: `RSASSA_PSS_SHA_256`
- **Priority**: If `ED25519_PRIVATE_KEY_HEX` is set, it takes priority over KMS. KMS is used only
  when the Ed25519 key is absent (e.g., during key rotation transition windows).
- **IAM**: The ECS task execution role must have `kms:Sign` permission on the key ARN.
- KMS keys are automatically rotated yearly by AWS when key rotation is enabled.

---

## 4. Key Rotation Procedure (condensed)

See [ROTATION_POLICY.md](ROTATION_POLICY.md) for the full runbook.

Summary:
1. Generate new key material.
2. Update SSM SecureString parameter.
3. Force a new ECS task deployment (picks up SSM values at startup).
4. Verify signing (`POST /field/v1/verify`) before declaring rotation complete.
5. Record rotation in the KCP key chain (`kcp/rotation_handler.py::rotate_key()`).
6. The `check_key_age()` job runs every 24 h and logs a WARNING when any key exceeds its
   `KEY_MAX_AGE_DAYS` threshold (default 330 days for Ed25519).

---

## 5. Secrets Management — SSM Parameter Store

All secrets are stored as `SecureString` values under `/myntist/beacon/`. The ECS task role has
read-only access. **No secrets are baked into the container image or task-definition environment
variables in plaintext.**

| SSM path | Secret | Rotation |
|---|---|---|
| `/myntist/beacon/DATABASE_URL` | PostgreSQL connection string | Quarterly |
| `/myntist/beacon/ED25519_PRIVATE_KEY_HEX` | Ed25519 private key (hex) | Annual |
| `/myntist/beacon/ED25519_KEY_CREATED` | ISO date of key creation | Updated on each rotation |
| `/myntist/beacon/SUBSTRATE_HMAC_SECRET` | Webhook HMAC secret | Quarterly |
| `/myntist/beacon/ADMIN_API_KEY` | Admin endpoint key | Quarterly |
| `/myntist/beacon/GODADDY_API_KEY` | GoDaddy DNS API key | Annual |
| `/myntist/beacon/GODADDY_API_SECRET` | GoDaddy DNS API secret | Annual |

---

## 6. Access Control

- **Admin endpoints** (`GET /policy/rules`): Requires `X-Admin-Key` header matching `ADMIN_API_KEY`.
  Returns HTTP 401 (missing) or HTTP 403 (wrong value). Key stored in SSM.
- **Unauthenticated endpoints**: All public field endpoints (`/field/v1/*`, `/health`, `/metrics`)
  are rate-limited by the ALB and require no auth.
- **ECS task IAM role**: `myntist-beacon-task-role` — least-privilege; read-only SSM + S3 put for
  the feeds bucket + optional KMS sign.
- **RDS**: Application connects as user `myntist` with `SELECT`, `INSERT` on relevant tables.
  `UPDATE` and `DELETE` on `iam_substrate_log` are revoked (see §8 Database Security).

---

## 7. CORS Configuration

The FastAPI application uses `CORSMiddleware` with the following settings
(configured in `iam_substrate/substrate_api/main.py`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

All origins are currently permitted because the field status endpoints are intended to be
publicly readable by any sovereign beacon client. If a private deployment is required, restrict
`allow_origins` to the specific frontend domain and set `CORS_ALLOW_ORIGINS` accordingly.
The ALB sits in front and provides the primary network-layer protection.

---

## 8. Database Security — Append-Only Audit Log

The `iam_substrate_log` table is **append-only** — enforced at the database level:

- **Trigger function**: `deny_audit_mutation()` — raises an exception for any UPDATE or DELETE.
- **Two BEFORE triggers**: `trg_audit_no_update` (BEFORE UPDATE) and `trg_audit_no_delete`
  (BEFORE DELETE) on `iam_substrate_log`.
- **REVOKE**: `UPDATE` and `DELETE` privileges are revoked from the `myntist` application role.
- **Migration**: `infra/sql/001_audit_log_append_only.sql` (idempotent, re-runnable).
  Also available as Alembic revision `001` in `iam_substrate/alembic/versions/`.

Telemetry rows are pruned after `TELEMETRY_RETENTION_HOURS` (default 24 h) to limit
data exposure. No PII is stored — identity IDs are opaque UUIDs.
