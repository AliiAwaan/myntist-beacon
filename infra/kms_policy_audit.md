# KMS Key Policy Audit — trust-ledger-kms-key-01

**Date**: 2026-05-07
**Account**: 225161979546 (us-east-1)
**Auditor**: Automated — Myntist Sovereign Beacon Task #2

---

## ⚠️ OPEN ACTION REQUIRED — Operator Must Run Steps Below

Direct AWS API access from the Replit workspace returns `InvalidSignatureException`
because the stored credential (`AWS_API_KEY`) is scoped to the ECS task boundary and
cannot make KMS API calls from outside that boundary.

**An operator with the `kms:GetKeyPolicy` and `kms:DescribeKey` IAM permissions must
run the commands in the "Manual Retrieval" section below, paste the output into the
"Actual Policy (Operator Fill-In)" section, and tick each checklist item.**

---

## Manual Retrieval Commands

```bash
#!/usr/bin/env bash
# Run this as an operator with IAM access to account 225161979546

export AWS_DEFAULT_REGION=us-east-1

# 1. Find the key ID for the trust-ledger alias
KEY_ID=$(aws kms describe-key \
  --key-id alias/trust-ledger-kms-key-01 \
  --query 'KeyMetadata.KeyId' --output text)
echo "Key ID: $KEY_ID"

# 2. Get key metadata
aws kms describe-key \
  --key-id alias/trust-ledger-kms-key-01 \
  --query 'KeyMetadata.{KeyId:KeyId,KeyUsage:KeyUsage,KeySpec:KeySpec,Enabled:Enabled,KeyRotationEnabled:KeyRotationEnabled}' \
  --output json

# 3. Check rotation status
aws kms get-key-rotation-status \
  --key-id alias/trust-ledger-kms-key-01

# 4. Retrieve the default key policy
aws kms get-key-policy \
  --key-id alias/trust-ledger-kms-key-01 \
  --policy-name default \
  --query Policy --output text | python3 -m json.tool

# 5. Check CloudTrail logging for KMS management events
aws cloudtrail get-event-selectors \
  --trail-name management-events \
  --query 'EventSelectors[*].{ReadWrite:ReadWriteType,MgmtEvents:IncludeManagementEvents}' \
  --output json 2>/dev/null || echo "(check CloudTrail console for KMS event coverage)"
```

---

## Actual Policy (Operator Fill-In)

```
PASTE OUTPUT OF: aws kms get-key-policy --key-id alias/trust-ledger-kms-key-01 --policy-name default --query Policy --output text | python3 -m json.tool
```

---

## Recommended Policy (Expected State)

The key is used for `RSASSA_PSS_SHA_256` payload signing by the Myntist Beacon ECS task.
The policy should match this least-privilege model exactly:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountRootForAdmin",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::225161979546:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "AllowEcsTaskRoleToSign",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::225161979546:role/myntist-beacon-task-role"
      },
      "Action": [
        "kms:Sign",
        "kms:GetPublicKey",
        "kms:DescribeKey"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenySignFromNonEcsPrincipals",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "kms:Sign",
      "Resource": "*",
      "Condition": {
        "ArnNotLike": {
          "aws:PrincipalArn": [
            "arn:aws:iam::225161979546:root",
            "arn:aws:iam::225161979546:role/myntist-beacon-task-role"
          ]
        }
      }
    }
  ]
}
```

---

## Verification Checklist

| # | Check | Expected | Operator Finding | Status |
|---|---|---|---|---|
| 1 | Key usage (`KeyUsage`) | `SIGN_VERIFY` | _paste here_ | ⬜ |
| 2 | Key spec (`KeySpec`) | `RSA_2048` or `RSA_3072` | _paste here_ | ⬜ |
| 3 | Key enabled (`Enabled`) | `true` | _paste here_ | ⬜ |
| 4 | Automatic rotation enabled | `true` (yearly) | _paste here_ | ⬜ |
| 5 | Only `myntist-beacon-task-role` has `kms:Sign` | Yes | _paste here_ | ⬜ |
| 6 | No wildcard `*` principals in Allow (except root) | Yes | _paste here_ | ⬜ |
| 7 | `DenySignFromNonEcsPrincipals` Deny SID present | Yes | _paste here_ | ⬜ |
| 8 | CloudTrail logs KMS management events | Yes | _paste here_ | ⬜ |
| 9 | No cross-account principals in policy | Yes | _paste here_ | ⬜ |

**To enable automatic rotation (if not already set):**
```bash
aws kms enable-key-rotation \
  --key-id alias/trust-ledger-kms-key-01 \
  --region us-east-1
```

---

## Gap Remediation Script

If the actual policy has deviations from the recommended policy, run:

```bash
# Construct the recommended policy and apply it
POLICY=$(cat << 'EOPOLICY'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountRootForAdmin",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::225161979546:root"},
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "AllowEcsTaskRoleToSign",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::225161979546:role/myntist-beacon-task-role"},
      "Action": ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"],
      "Resource": "*"
    },
    {
      "Sid": "DenySignFromNonEcsPrincipals",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "kms:Sign",
      "Resource": "*",
      "Condition": {
        "ArnNotLike": {
          "aws:PrincipalArn": [
            "arn:aws:iam::225161979546:root",
            "arn:aws:iam::225161979546:role/myntist-beacon-task-role"
          ]
        }
      }
    }
  ]
}
EOPOLICY
)

aws kms put-key-policy \
  --key-id alias/trust-ledger-kms-key-01 \
  --policy-name default \
  --policy "$POLICY" \
  --region us-east-1
```

---

## Blocker Status

This item is **BLOCKED** pending operator execution of the manual retrieval steps above.
The code-retrievable form of the policy cannot be obtained without valid IAM credentials
that can make KMS API calls from outside the ECS task boundary.

**Acceptance**: Item is considered CLOSED when an operator fills in the "Actual Policy"
section, ticks all 9 checklist items, and commits the updated file to this repository.
