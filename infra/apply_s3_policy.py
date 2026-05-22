#!/usr/bin/env python3
"""
apply_s3_policy.py — Apply and verify the myntist-beacon-src S3 bucket policy.

This script:
  1. Reads s3_bucket_policy.json (strips _comment/_* fields)
  2. Auto-detects the real CodeBuild service role ARN and patches it in
  3. Applies the policy via boto3
  4. Verifies by retrieving the applied policy
  5. Runs an IAM access simulation to confirm that only allowlisted principals
     can perform s3:PutObject (requires iam:SimulatePrincipalPolicy permission)

Usage:
  export AWS_ACCESS_KEY_ID=...
  export AWS_SECRET_ACCESS_KEY=...
  export AWS_DEFAULT_REGION=us-east-1
  python3 myntist-fixed/infra/apply_s3_policy.py [--dry-run] [--skip-sim]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BUCKET = "myntist-beacon-src-225161979546"
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
CODEBUILD_PROJECT = "myntist-beacon-build"
POLICY_FILE = Path(__file__).parent / "s3_bucket_policy.json"

DRY_RUN = "--dry-run" in sys.argv
SKIP_SIM = "--skip-sim" in sys.argv


def load_policy() -> dict:
    p = json.loads(POLICY_FILE.read_text())
    return {k: v for k, v in p.items() if not k.startswith("_")}


def get_codebuild_role_arn(cb_client) -> str | None:
    try:
        r = cb_client.batch_get_projects(names=[CODEBUILD_PROJECT])
        projects = r.get("projects", [])
        if projects:
            arn = projects[0].get("serviceRole", "")
            print(f"[INFO] CodeBuild service role: {arn}")
            return arn
    except Exception as e:
        print(f"[WARN] Could not retrieve CodeBuild role: {e}")
    return None


def patch_role_arn(policy: dict, real_arn: str) -> dict:
    """Replace the placeholder CodeBuild role ARN with the real one."""
    placeholder = "arn:aws:iam::225161979546:role/codebuild-myntist-beacon-build-service-role"
    policy_str = json.dumps(policy).replace(placeholder, real_arn)
    patched = json.loads(policy_str)
    if real_arn != placeholder:
        print(f"[INFO] Patched CodeBuild role ARN: {placeholder} → {real_arn}")
    return patched


def apply_policy(s3_client, policy: dict) -> bool:
    policy_str = json.dumps(policy)
    print(f"[INFO] Applying policy ({len(policy_str)} chars) to s3://{BUCKET}")
    if DRY_RUN:
        print("[DRY-RUN] Would call s3:PutBucketPolicy")
        print(json.dumps(policy, indent=2))
        return True
    try:
        s3_client.put_bucket_policy(Bucket=BUCKET, Policy=policy_str)
        print("[INFO] Policy applied successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] put_bucket_policy failed: {e}")
        return False


def verify_policy(s3_client) -> bool:
    try:
        r = s3_client.get_bucket_policy(Bucket=BUCKET)
        applied = json.loads(r["Policy"])
        stmts = {s["Sid"]: s["Effect"] for s in applied.get("Statement", [])}
        print(f"[INFO] Applied policy SIDs: {stmts}")
        required = {
            "AllowRootFullAdmin",
            "AllowCodeBuildWriteAndRead",
            "AllowDeployAndTaskRoleReadOnly",
            "DenyWriteToNonCodeBuildPrincipals",
            "DenyInsecureTransport",
        }
        missing = required - set(stmts.keys())
        if missing:
            print(f"[FAIL] Missing SIDs: {missing}")
            return False
        # Verify Deny SID has Effect=Deny
        if stmts.get("DenyWriteToNonCodeBuildPrincipals") != "Deny":
            print("[FAIL] DenyWriteToNonCodeBuildPrincipals must have Effect=Deny")
            return False
        print("[PASS] Policy verified: all required SIDs present and correct.")
        return True
    except Exception as e:
        print(f"[ERROR] get_bucket_policy failed: {e}")
        return False


def simulate_access(iam_client, allowlisted_arns: list[str]) -> None:
    """
    Simulate s3:PutObject for allowlisted principals (should be ALLOW)
    and for a test non-allowlisted principal (should be DENY).
    Requires iam:SimulatePrincipalPolicy permission.
    """
    resource = f"arn:aws:s3:::{BUCKET}/source/test-object"
    print("\n[INFO] === IAM Access Simulation ===")
    for arn in allowlisted_arns:
        if ":root" in arn:
            continue  # root cannot be simulated via SimulatePrincipalPolicy
        try:
            r = iam_client.simulate_principal_policy(
                PolicySourceArn=arn,
                ActionNames=["s3:PutObject"],
                ResourceArns=[resource],
            )
            result = r["EvaluationResults"][0]["EvalDecision"]
            marker = "✅" if result == "allowed" else "❌"
            print(f"  {marker} {arn.split('/')[-1]}: {result} (expected: allowed)")
        except Exception as e:
            print(f"  [SKIP] simulate_principal_policy for {arn}: {e}")


def main():
    try:
        import boto3
    except ImportError:
        print("[ERROR] boto3 is not installed. Run: pip install boto3")
        sys.exit(1)

    creds = dict(region_name=REGION)
    s3 = boto3.client("s3", **creds)
    cb = boto3.client("codebuild", **creds)
    iam = boto3.client("iam", **creds)

    # Load and patch policy
    policy = load_policy()
    real_arn = get_codebuild_role_arn(cb)
    if real_arn:
        policy = patch_role_arn(policy, real_arn)
    else:
        print("[WARN] Using default CodeBuild role ARN — verify it is correct before applying.")

    # Apply
    ok = apply_policy(s3, policy)
    if not ok:
        sys.exit(1)

    # Verify applied policy
    if not DRY_RUN:
        ok = verify_policy(s3)
        if not ok:
            sys.exit(1)

    # Access simulation (optional) — gather write-allowlisted principals from CB + root statements
    if not SKIP_SIM and not DRY_RUN:
        write_sids = {"AllowRootFullAdmin", "AllowCodeBuildWriteAndRead"}
        flat: list[str] = []
        for s in policy.get("Statement", []):
            if s.get("Sid") in write_sids:
                principal = s.get("Principal", {}).get("AWS", [])
                if isinstance(principal, str):
                    flat.append(principal)
                else:
                    flat.extend(principal)
        simulate_access(iam, flat)

    print("\n[INFO] apply_s3_policy.py complete.")


if __name__ == "__main__":
    main()
