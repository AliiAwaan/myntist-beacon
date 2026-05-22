# Deployment Guide — Myntist Sovereign Beacon

## Architecture Overview

```
Internet
  └─ ALB  (myntist-beacon-alb-288532976.us-east-1.elb.amazonaws.com)
       └─ ECS Fargate  (cluster: myntist-beacon, service: myntist-beacon-api)
            ├─ Docker container  (ECR: 225161979546.dkr.ecr.us-east-1.amazonaws.com/myntist-beacon)
            └─ PostgreSQL RDS  (myntist-beacon-db.cljxxseopmqu.us-east-1.rds.amazonaws.com)
```

## Hybrid Deployment Model

The infrastructure uses a **hybrid approach** combining three distinct deployment methods:

### 1. CloudFormation — Networking & IAM (managed)

The VPC, subnets, security groups, ALB, ECS cluster, and IAM roles are provisioned via
CloudFormation. Two stack deployments were attempted before reaching the current stable state:

- **Stack attempt 1**: Failed on the RDS subnet group — the AZ spread did not include
  `us-east-1a` which the chosen instance class required.
- **Stack attempt 2**: Failed on the ECS service stabilisation timeout — the initial task
  definition referenced a non-existent ECR image tag before the first CodeBuild run completed.
- **Current stable state**: Networking, IAM roles, and the ALB are managed by the surviving
  CFn stack. The ECS service and task definitions are managed **outside** CloudFormation
  (updated manually via AWS CLI and the CodeBuild pipeline) to avoid the stabilisation timeout
  issue. Do **not** re-import the service resource into the stack without first ensuring the
  ECR image exists.

### 2. Manual RDS Setup

The PostgreSQL RDS instance (`myntist-beacon-db`) was created manually via the AWS Console
because the CFn `AWS::RDS::DBInstance` resource triggered the subnet-group AZ conflict.
Key configuration:
- Engine: PostgreSQL 15.x
- Instance class: `db.t3.micro`
- Storage: 20 GiB gp3, encrypted at rest
- Private subnet, no public IP — accessible only from the ECS security group
- Master user: `myntist` — application user with restricted DML (see §Database Migrations)

### 3. CodeBuild — Application Layer (automated)

The Python API and React dashboard are built and deployed via CodeBuild:

- **Source**: S3 ZIP at `s3://myntist-beacon-src-225161979546/source/myntist-source.zip`
- **Buildspec**: `myntist-fixed/infra/buildspec.yml` (`SRC=myntist-fixed`)
- **Output**: Docker image pushed to ECR, new ECS task definition registered, service updated

---

## Prerequisites

- AWS CLI configured for account `225161979546`, region `us-east-1`
- Docker (for local image builds)
- Python 3.11+ with `requirements.txt` installed (local testing)
- `pnpm` (for dashboard builds)

---

## Environment Variables & Secrets

All production secrets are stored in **AWS SSM Parameter Store** as `SecureString` values.
Copy `.env.example` to `.env` for local development — **never commit `.env`**.

| Variable | SSM path | Description |
|---|---|---|
| `DATABASE_URL` | `/myntist/beacon/DATABASE_URL` | PostgreSQL connection string |
| `ED25519_PRIVATE_KEY_HEX` | `/myntist/beacon/ED25519_PRIVATE_KEY_HEX` | Ed25519 private key (hex) |
| `ED25519_KEY_CREATED` | `/myntist/beacon/ED25519_KEY_CREATED` | ISO date of key creation |
| `SUBSTRATE_HMAC_SECRET` | `/myntist/beacon/SUBSTRATE_HMAC_SECRET` | Webhook HMAC secret |
| `ADMIN_API_KEY` | `/myntist/beacon/ADMIN_API_KEY` | Admin endpoint key |
| `GODADDY_API_KEY` | `/myntist/beacon/GODADDY_API_KEY` | GoDaddy DNS API key |
| `GODADDY_API_SECRET` | `/myntist/beacon/GODADDY_API_SECRET` | GoDaddy DNS API secret |
| `S3_BUCKET` | Task-def env var | Bucket for status.json and ledger output |
| `CANONICAL_URL` | Task-def env var | Full URL of the status.json endpoint |

---

## Local Development

```bash
cd myntist-fixed/myntist-beacon

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, ED25519_PRIVATE_KEY_HEX, etc.

# Apply DB schema + append-only trigger
cd iam_substrate
alembic upgrade head
# or: psql $DATABASE_URL -f ../infra/sql/001_audit_log_append_only.sql

# Run the API
uvicorn iam_substrate.substrate_api.main:app --reload --port 8000

# Run tests
cd ..
pytest tests/ -v --tb=short
```

---

## Deploy Pipeline (CodeBuild → ECS)

### 1. Upload source to S3

```bash
cd /home/runner/workspace
zip -r /tmp/myntist-source.zip myntist-fixed/ \
  -x "*.pyc" -x "*/__pycache__/*" -x "*.egg-info/*" -x ".git/*"

aws s3 cp /tmp/myntist-source.zip \
  s3://myntist-beacon-src-225161979546/source/myntist-source.zip
```

### 2. Trigger CodeBuild

```bash
BUILD_ID=$(aws codebuild start-build \
  --project-name myntist-beacon-build \
  --region us-east-1 \
  --query 'build.id' --output text)

# Poll for completion
aws codebuild batch-get-builds --ids "$BUILD_ID" \
  --query 'builds[0].{status:buildStatus,phase:currentPhase}'
```

The buildspec (`infra/buildspec.yml`) runs `pytest`, builds the Docker image, pushes to ECR,
registers a new ECS task definition revision, and updates the ECS service (rolling deploy).

### 3. Manual ECS service update (if bypassing CodeBuild)

```bash
aws ecs update-service \
  --cluster myntist-beacon \
  --service myntist-beacon-api \
  --task-definition myntist-beacon-task:<NEW_REV> \
  --region us-east-1
```

---

## Database Migrations

**Canonical Alembic location**: `myntist-fixed/myntist-beacon/alembic/` (with `alembic.ini` at
`myntist-fixed/myntist-beacon/alembic.ini`). This is the single source of truth for all migrations.
The directory `iam_substrate/alembic/` also exists as an integration-test fixture for the FastAPI
package; operators should **not** run `alembic upgrade head` from that path in production.

Schema changes are managed via **Alembic** in `myntist-fixed/myntist-beacon/alembic/`.

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new autogenerate migration
alembic revision --autogenerate -m "describe change"

# Rollback one step
alembic downgrade -1
```

The raw SQL file `infra/sql/001_audit_log_append_only.sql` can be applied directly when
Alembic is unavailable — it is idempotent and safe to re-run.

---

## Rollback

See [myntist-beacon/RUNBOOKS.md](myntist-beacon/RUNBOOKS.md) §4 for the ECS rollback procedure.

## Security & Key Rotation

See [myntist-beacon/SECURITY.md](myntist-beacon/SECURITY.md) and
[myntist-beacon/ROTATION_POLICY.md](myntist-beacon/ROTATION_POLICY.md).
