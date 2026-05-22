# Deployment Guide — Myntist Sovereign Beacon

## Architecture

```
Internet → ALB (myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com)
             └─ ECS Fargate (cluster: myntist-beacon, service: myntist-beacon-api)
                  └─ Docker container (ECR: 225161979546.dkr.ecr.us-east-1.amazonaws.com/myntist-beacon)
                       └─ PostgreSQL (RDS: myntist-beacon-db.cljxxseopmqu.us-east-1.rds.amazonaws.com)
```

CodeBuild pipeline: S3 ZIP → Docker build → ECR push → ECS task-def update → service update.

---

## Prerequisites

- AWS CLI configured for account `225161979546`, region `us-east-1`
- Docker (for local builds)
- `pnpm` (for dashboard builds)
- Python 3.11+ with `requirements.txt` installed (for local testing)

---

## Environment Variables

All production secrets are stored in **AWS SSM Parameter Store** as `SecureString` values.
The ECS task definition's `secrets` block injects them at container startup.

Copy `.env.example` to `.env` for local development — never commit `.env`.

Key variables:

| Variable | SSM path | Description |
|---|---|---|
| `DATABASE_URL` | `/myntist/beacon/DATABASE_URL` | PostgreSQL connection string |
| `ED25519_PRIVATE_KEY_HEX` | `/myntist/beacon/ED25519_PRIVATE_KEY_HEX` | 32-byte Ed25519 private key (hex) |
| `ED25519_KEY_CREATED` | `/myntist/beacon/ED25519_KEY_CREATED` | ISO date of key creation |
| `SUBSTRATE_HMAC_SECRET` | `/myntist/beacon/SUBSTRATE_HMAC_SECRET` | Webhook HMAC secret |
| `ADMIN_API_KEY` | `/myntist/beacon/ADMIN_API_KEY` | Admin endpoint key |
| `GODADDY_API_KEY` | `/myntist/beacon/GODADDY_API_KEY` | GoDaddy DNS API key |
| `GODADDY_API_SECRET` | `/myntist/beacon/GODADDY_API_SECRET` | GoDaddy DNS API secret |
| `S3_BUCKET` | env var in task def | Bucket for status.json and ledger output |
| `CANONICAL_URL` | env var in task def | Full URL of the status.json endpoint |

---

## Local Development

```bash
# 1. Install Python dependencies
cd myntist-fixed/myntist-beacon
pip install -r requirements.txt

# 2. Copy and configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, ED25519_PRIVATE_KEY_HEX, etc.

# 3. Apply DB schema
cd iam_substrate
alembic upgrade head
# or: psql $DATABASE_URL -f infra/sql/001_audit_log_append_only.sql

# 4. Run the API server
uvicorn iam_substrate.substrate_api.main:app --reload --port 8000

# 5. Run tests
cd myntist-fixed/myntist-beacon
pytest tests/ -v
```

---

## CI/CD Pipeline (CodeBuild → ECS)

### Source Upload

```bash
cd /home/runner/workspace
zip -r /tmp/myntist-source.zip myntist-fixed/ \
  -x "*.pyc" -x "*/__pycache__/*" -x "*.egg-info/*" -x ".git/*"

aws s3 cp /tmp/myntist-source.zip \
  s3://myntist-beacon-src-225161979546/source/myntist-source.zip
```

### Trigger Build

```bash
BUILD_ID=$(aws codebuild start-build \
  --project-name myntist-beacon-build \
  --region us-east-1 \
  --query 'build.id' --output text)

echo "Build: $BUILD_ID"

# Poll for completion
aws codebuild batch-get-builds --ids "$BUILD_ID" \
  --query 'builds[0].{status:buildStatus,phase:currentPhase}' --output table
```

The buildspec at `infra/buildspec.yml` will:
1. Install Python + Node.js dependencies
2. Run `pytest` (build fails if any test fails)
3. Build the Docker image and push to ECR
4. Register a new ECS task definition revision
5. Update the ECS service (rolling deploy, 0 downtime)

### Manual Service Update (if buildspec already pushed the image)

```bash
IMAGE_TAG="20260507110908"  # replace with actual tag
ECR="225161979546.dkr.ecr.us-east-1.amazonaws.com/myntist-beacon"

# Register new task def revision with new image
# (Use infra/deploy.sh or the Node.js script in /tmp/aws-deploy2)

# Update service
aws ecs update-service \
  --cluster myntist-beacon \
  --service myntist-beacon-api \
  --task-definition myntist-beacon-task:<NEW_REV> \
  --region us-east-1
```

---

## Database Migrations

Schema changes are managed via **Alembic** (located in `iam_substrate/alembic/`).

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "describe change"

# Rollback one step
alembic downgrade -1
```

The raw SQL trigger migration is also available at `infra/sql/001_audit_log_append_only.sql`
and can be applied directly if Alembic is not available.

---

## Monitoring

- **CloudWatch Logs**: `/ecs/myntist-beacon`
- **Prometheus metrics**: `GET /api/metrics`
- **ALB health check**: `GET /api/health` → must return HTTP 200

See [RUNBOOKS.md](RUNBOOKS.md) for alert response procedures.

---

## Security

See [SECURITY.md](SECURITY.md) for key rotation, secrets management, and vulnerability
reporting.

See [ROTATION_POLICY.md](ROTATION_POLICY.md) for the key rotation schedule.
