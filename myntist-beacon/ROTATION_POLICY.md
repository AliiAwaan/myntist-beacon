# Key Rotation Policy — Myntist Sovereign Beacon

## Overview

This document defines rotation schedules, procedures, and verification steps for all secrets
used by the Myntist Sovereign Beacon. Rotation is enforced by the `check_key_age()` function
(in `kcp/rotation_handler.py`) which runs every 24 hours and logs a WARNING when any key exceeds
its maximum age.

---

## Rotation Schedule

| Secret | SSM path | Rotation frequency | Trigger threshold |
|--------|----------|-------------------|-------------------|
| Ed25519 private key | `/myntist/beacon/ED25519_PRIVATE_KEY_HEX` | **Annual** (every 365 days) | >330 days old |
| HMAC webhook secret | `/myntist/beacon/SUBSTRATE_HMAC_SECRET` | **Quarterly** (every 90 days) | >80 days old |
| Admin API key | `/myntist/beacon/ADMIN_API_KEY` | **Quarterly** (every 90 days) | >80 days old |
| DATABASE_URL / DB password | `/myntist/beacon/DATABASE_URL` | **Quarterly** (every 90 days) | Policy-based |
| GoDaddy API key/secret | `/myntist/beacon/GODADDY_API_KEY`, `GODADDY_API_SECRET` | **Annual** | Policy-based |
| KMS CMK | AWS KMS (ARN in `KMS_KEY_ID`) | **Automatic** (yearly, AWS-managed) | N/A |
| KCP genesis key | JSON flat-file / DB | Per governance policy | Per KeyState chain |

---

## Ed25519 Signing Key — Annual Rotation

### Prerequisites
- AWS CLI access to account 225161979546 (us-east-1)
- Permission to write SSM parameters under `/myntist/beacon/`

### Procedure

1. **Generate a new Ed25519 key pair**
   ```bash
   python - <<'EOF'
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   import binascii, datetime
   k = Ed25519PrivateKey.generate()
   priv_hex = binascii.hexlify(k.private_bytes_raw()).decode()
   pub_hex  = binascii.hexlify(k.public_key().public_bytes_raw()).decode()
   print("PRIVATE:", priv_hex)
   print("PUBLIC: ", pub_hex)
   print("CREATED:", datetime.date.today().isoformat())
   EOF
   ```

2. **Update SSM parameters**
   ```bash
   aws ssm put-parameter \
     --name /myntist/beacon/ED25519_PRIVATE_KEY_HEX \
     --value "<new-private-hex>" \
     --type SecureString --overwrite --region us-east-1

   aws ssm put-parameter \
     --name /myntist/beacon/ED25519_KEY_CREATED \
     --value "$(date +%Y-%m-%d)" \
     --type SecureString --overwrite --region us-east-1
   ```

3. **Force a new ECS deployment** (picks up new SSM values on startup)
   ```bash
   aws ecs update-service \
     --cluster myntist-beacon \
     --service myntist-beacon-api \
     --force-new-deployment \
     --region us-east-1
   ```

4. **Verify** — fetch `status.json`, then `POST /field/v1/verify` with the payload and
   signature; confirm `{ "valid": true }`.

5. **Record in KCP key chain**
   ```python
   from kcp.rotation_handler import rotate_key
   rotate_key(new_public_key="<new-public-hex>")
   ```

---

## HMAC Webhook Secret — Quarterly Rotation

1. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Update SSM: `/myntist/beacon/SUBSTRATE_HMAC_SECRET`
3. Update the same value in Keycloak or any system sending `POST /events` webhooks.
4. Deploy new ECS task revision (zero-downtime; old tasks drain within 30 s).
5. Verify: send a signed test event and confirm HTTP 201.

---

## Admin API Key — Quarterly Rotation

1. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Update SSM: `/myntist/beacon/ADMIN_API_KEY`
3. Distribute the new key to all callers of `GET /policy/rules`.
4. Deploy new ECS task revision.
5. Verify: `curl -H "X-Admin-Key: <new-key>" /api/policy/rules` returns HTTP 200.

---

## Database URL / Password — Quarterly Rotation

The `DATABASE_URL` encodes the PostgreSQL password. To rotate:

1. **Generate a new password** (≥ 32 random characters):
   ```bash
   python -c "import secrets, string; print(secrets.token_urlsafe(32))"
   ```

2. **Update the RDS user password**
   ```bash
   psql $OLD_DATABASE_URL -c "ALTER USER myntist PASSWORD '<new-password>';"
   ```

3. **Update the SSM parameter** with the new URL:
   ```bash
   NEW_URL="postgresql://myntist:<new-password>@myntist-beacon-db.cljxxseopmqu.us-east-1.rds.amazonaws.com:5432/myntist_beacon"
   aws ssm put-parameter \
     --name /myntist/beacon/DATABASE_URL \
     --value "$NEW_URL" \
     --type SecureString --overwrite --region us-east-1
   ```

4. **Deploy new ECS task revision** (reads SSM on startup).
5. **Verify** health: `GET /api/health` → `{ "status": "ok" }`.

---

## KCP Key Rotation

The Key Continuity Protocol maintains a hash-chained key-state ledger. Call `rotate_key()`
in `kcp/rotation_handler.py` with the new public key. The rotation appends a new `KeyState`
with `parent_key_state_hash` pointing to the prior state, preserving auditability.

```python
from kcp.rotation_handler import rotate_key
new_state = rotate_key(new_public_key="<new-public-hex>")
print(f"New KCP version: {new_state.version}")
```

---

## Rollback Procedure

If a rotated key causes failures:

1. Re-put the prior value from a secure backup into SSM.
2. Force a new ECS deployment.
3. Verify signing and HMAC before declaring the incident closed.
4. File a post-mortem and update this document with the lesson learned.
