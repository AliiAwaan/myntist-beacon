# Test Coverage Report — Myntist Sovereign Beacon

**Date**: 2026-05-07
**Run**: `python3 -m pytest tests/ --cov=beacon_core --cov=iam_substrate --cov=kcp --cov=identity_loop --cov-report=term-missing -q`
**Result**: ✅ **90%** (1874 / 2082 statements covered)
**Tests**: 425 passed, 0 failed

---

## Module Breakdown

| Module | Stmts | Miss | Cover | Notes |
|---|---|---|---|---|
| `beacon_core/dns/godaddy_updater.py` | 50 | 1 | **98%** | |
| `beacon_core/dossier/__init__.py` | 0 | 0 | **100%** | |
| `beacon_core/dossier/config.py` | 7 | 0 | **100%** | |
| `beacon_core/hsce/interface_contract.py` | 45 | 0 | **100%** | |
| `beacon_core/lambdas/export_parquet/handler.py` | 69 | 2 | **97%** | Was 26% — fixed round 4 |
| `beacon_core/lambdas/generate_benchmarks/handler.py` | 52 | 31 | 40% | AWS-only paths require live CloudWatch |
| `beacon_core/lambdas/generate_float_ledger/handler.py` | 70 | 0 | **100%** | Was 29% — fixed round 4 |
| `beacon_core/lambdas/generate_matrix/handler.py` | 75 | 53 | 29% | AWS-only paths require live DynamoDB |
| `beacon_core/lambdas/generate_pulse/handler.py` | 65 | 42 | 35% | AWS-only paths require live Kinesis |
| `beacon_core/lambdas/generate_status/handler.py` | 125 | 1 | **99%** | Was 70% — fixed round 4 |
| `beacon_core/signing/ed25519_signer.py` | 65 | 0 | **100%** | Was 97% — fixed round 4 |
| `beacon_core/signing/field_signing_keys.py` | 5 | 0 | **100%** | Was 80% — fixed round 4 |
| `beacon_core/signing/kms_signer.py` | 33 | 2 | **94%** | KMS hardware boundary |
| `beacon_core/telemetry/financial_engine.py` | 63 | 6 | **90%** | |
| `beacon_core/telemetry/financial_validator.py` | 36 | 1 | **97%** | |
| `beacon_core/telemetry/survivability_engine.py` | 39 | 1 | **97%** | |
| `beacon_core/telemetry/telemetry_exporter.py` | 113 | 3 | **97%** | Was 80% — fixed round 4 |
| `iam_substrate/ledger/audit_log.py` | 23 | 0 | **100%** | |
| `iam_substrate/substrate_api/autoheal.py` | 69 | 15 | 78% | GitHub App credential boundary |
| `iam_substrate/substrate_api/database.py` | 56 | 14 | 75% | Was 52% — fixed round 4 |
| `iam_substrate/substrate_api/main.py` | 324 | 18 | **94%** | Was 64% — fixed round 4 |
| `iam_substrate/substrate_api/models.py` | 47 | 0 | **100%** | |
| `iam_substrate/substrate_api/policy_engine.py` | 126 | 11 | **91%** | Was 79% — fixed round 4 |
| `iam_substrate/substrate_api/role_decay.py` | 151 | 7 | **95%** | |
| `iam_substrate/substrate_api/scoring.py` | 15 | 0 | **100%** | |
| `iam_substrate/substrate_api/telemetry_emitter.py` | 14 | 0 | **100%** | |
| `iam_substrate/webhooks/hmac_handler.py` | 24 | 0 | **100%** | |
| `identity_loop/feeds/farcaster_adapter.py` | 27 | 0 | **100%** | Was 0% — fixed round 4 |
| `identity_loop/feeds/lens_adapter.py` | 37 | 0 | **100%** | Was 0% — fixed round 4 |
| `identity_loop/feeds/rss_generator.py` | 56 | 0 | **100%** | Was 0% — fixed round 4 |
| `identity_loop/well_known/signing_keys_publisher.py` | 24 | 0 | **100%** | Was 0% — fixed round 4 |
| `identity_loop/zenodo/ipfs_pinner.py` | 25 | 0 | **100%** | Was 52% — fixed round 4 |
| `identity_loop/zenodo/zenodo_client.py` | 27 | 0 | **100%** | Was 44% — fixed round 4 |
| `kcp/continuity_verifier.py` | 36 | 0 | **100%** | |
| `kcp/key_state.py` | 45 | 0 | **100%** | |
| `kcp/rotation_handler.py` | 44 | 0 | **100%** | Was 98% — fixed round 4 |
| **TOTAL** | **2082** | **208** | **90%** | ✅ Exceeds ≥90% requirement |

---

## Modules at 100% Coverage (19 modules)

- `beacon_core/dossier/__init__.py`
- `beacon_core/dossier/config.py`
- `beacon_core/hsce/interface_contract.py`
- `beacon_core/signing/ed25519_signer.py`
- `beacon_core/signing/field_signing_keys.py`
- `beacon_core/lambdas/generate_float_ledger/handler.py`
- `iam_substrate/ledger/audit_log.py`
- `iam_substrate/substrate_api/models.py`
- `iam_substrate/substrate_api/scoring.py`
- `iam_substrate/substrate_api/telemetry_emitter.py`
- `iam_substrate/webhooks/hmac_handler.py`
- `identity_loop/feeds/farcaster_adapter.py`
- `identity_loop/feeds/lens_adapter.py`
- `identity_loop/feeds/rss_generator.py`
- `identity_loop/well_known/signing_keys_publisher.py`
- `identity_loop/zenodo/ipfs_pinner.py`
- `identity_loop/zenodo/zenodo_client.py`
- `kcp/continuity_verifier.py`
- `kcp/key_state.py`
- `kcp/rotation_handler.py`

---

## Coverage Improvement Summary (4 rounds)

| Module | Round 1 | Round 2 | Round 3 | Round 4 | Total Δ |
|---|---|---|---|---|---|
| `beacon_core/dns/godaddy_updater.py` | 88% | 88% | 88% | **98%** | +10pp |
| `beacon_core/dossier/config.py` | 0% | **100%** | 100% | 100% | +100pp |
| `beacon_core/hsce/interface_contract.py` | 53% | 53% | **100%** | 100% | +47pp |
| `beacon_core/lambdas/export_parquet/handler.py` | 26% | 26% | 26% | **97%** | +71pp |
| `beacon_core/lambdas/generate_float_ledger/handler.py` | 29% | 29% | 29% | **100%** | +71pp |
| `beacon_core/lambdas/generate_status/handler.py` | 22% | 22% | 70% | **99%** | +77pp |
| `beacon_core/signing/ed25519_signer.py` | 68% | 68% | 97% | **100%** | +32pp |
| `beacon_core/signing/field_signing_keys.py` | 80% | 80% | 80% | **100%** | +20pp |
| `beacon_core/signing/kms_signer.py` | 36% | **94%** | 94% | 94% | +58pp |
| `beacon_core/telemetry/telemetry_exporter.py` | 80% | 80% | 80% | **97%** | +17pp |
| `iam_substrate/substrate_api/autoheal.py` | 45% | 59% | **75%** | 78% | +33pp |
| `iam_substrate/substrate_api/database.py` | 52% | 52% | 61% | **75%** | +23pp |
| `iam_substrate/substrate_api/main.py` | 64% | 64% | 76% | **94%** | +30pp |
| `iam_substrate/substrate_api/policy_engine.py` | 79% | 79% | 79% | **91%** | +12pp |
| `iam_substrate/substrate_api/role_decay.py` | 46% | 54% | **95%** | 95% | +49pp |
| `identity_loop/feeds/farcaster_adapter.py` | 0% | 0% | 0% | **100%** | +100pp |
| `identity_loop/feeds/lens_adapter.py` | 0% | 0% | 0% | **100%** | +100pp |
| `identity_loop/feeds/rss_generator.py` | 0% | 0% | 0% | **100%** | +100pp |
| `identity_loop/well_known/signing_keys_publisher.py` | 0% | 0% | 0% | **100%** | +100pp |
| `identity_loop/zenodo/ipfs_pinner.py` | 52% | 52% | 52% | **100%** | +48pp |
| `identity_loop/zenodo/zenodo_client.py` | 44% | 44% | 44% | **100%** | +56pp |
| `kcp/key_state.py` | 96% | **100%** | 100% | 100% | +4pp |
| `kcp/rotation_handler.py` | 43% | **98%** | 98% | **100%** | +57pp |

---

## Residual Gaps and Justification

| Module | Miss Lines | Reason | Remediation Path |
|---|---|---|---|
| `beacon_core/lambdas/generate_benchmarks/handler.py:58–123` | 31 | CloudWatch put-metric paths; require live AWS | Integration test via CodeBuild |
| `beacon_core/lambdas/generate_matrix/handler.py:34–150` | 53 | DynamoDB batch-write paths; require live AWS | Integration test via CodeBuild |
| `beacon_core/lambdas/generate_pulse/handler.py:43–128` | 42 | Kinesis put-record paths; require live AWS | Integration test via CodeBuild |
| `beacon_core/lambdas/export_parquet/handler.py:62–67` | 2 | Exception path inside pyarrow write fallback | Negligible — covered 97% |
| `beacon_core/lambdas/generate_status/handler.py:175` | 1 | One-line exception re-raise in ledger anchor | Negligible — covered 99% |
| `beacon_core/signing/kms_signer.py:49–50` | 2 | KMS hardware boundary — exception re-raise | Requires live KMS key |
| `iam_substrate/substrate_api/autoheal.py:58–105` | 15 | GitHub PR creation flow | Requires live GH App credentials |
| `iam_substrate/substrate_api/database.py:22–93` | 14 | SQLAlchemy Postgres connection pool | Requires live RDS (`DATABASE_URL`) |
| `iam_substrate/substrate_api/main.py:114–135,174,323–325,527–533,605,624` | 18 | ECS startup paths reading SSM params | Covered by ECS task integration |

---

## Test File Index

| File | Tests | Focus |
|---|---|---|
| `tests/test_financial_engine.py` | 18 | Float yield, liquidity, HSCE computation |
| `tests/test_financial_validator.py` | 16 | RFC-002 payload validation |
| `tests/test_hmac_handler.py` | 9 | HMAC-SHA256 signing and verification |
| `tests/test_hsce_interface.py` | 11 | HSCE interface contract |
| `tests/test_kcp.py` | 7 | Key state, ContinuityVerifier invariants |
| `tests/test_policy_engine.py` | 16 | P001–P004 policy engine |
| `tests/test_rfc002_compliance.py` | 11 | RFC-002 compliance sections F–H |
| `tests/test_role_decay.py` | 13 | Role decay scan, telemetry round-robin |
| `tests/test_substrate_api.py` | 17 | FastAPI endpoints (health, events, score, telemetry) |
| `tests/test_survivability_engine.py` | 14 | S formula, field state, delta_S |
| `tests/test_telemetry_exporter.py` | 11 | In-memory telemetry store |
| `tests/test_coverage_gaps.py` | 37 | Targeted gap tests (round 2) |
| `tests/test_coverage_extended.py` | 32 | Extended gap tests (round 3) |
| `tests/test_coverage_round4.py` | (round 4 original) | Round 4 gap tests |
| `tests/test_identity_loop.py` | 39 | identity_loop feeds, zenodo, well-known (round 4 new) |
| `tests/test_lambda_handlers.py` | 45 | Lambda handler coverage: export_parquet, float_ledger, status (round 4 new) |
| `tests/test_coverage_boost.py` | 87 | policy_engine, database, main, telemetry_exporter, godaddy, rotation, signing (round 4 new) |
| **Total** | **425** | |

---

## pytest Command Transcript (Round 4)

```
$ python3 -m pytest tests/ \
    --cov=beacon_core --cov=iam_substrate --cov=kcp --cov=identity_loop \
    --cov-report=term-missing -q

...........................................................................
...........................................................................
...........................................................................
...........................................................................
...........................................................................
.................................................................
================================ tests coverage ================================
Name                                                   Stmts   Miss  Cover
----------------------------------------------------------------------
beacon_core/dns/godaddy_updater.py                        50      1    98%
beacon_core/dossier/__init__.py                            0      0   100%
beacon_core/dossier/config.py                              7      0   100%
beacon_core/hsce/interface_contract.py                    45      0   100%
beacon_core/lambdas/export_parquet/handler.py             69      2    97%
beacon_core/lambdas/generate_benchmarks/handler.py        52     31    40%
beacon_core/lambdas/generate_float_ledger/handler.py      70      0   100%
beacon_core/lambdas/generate_matrix/handler.py            75     53    29%
beacon_core/lambdas/generate_pulse/handler.py             65     42    35%
beacon_core/lambdas/generate_status/handler.py           125      1    99%
beacon_core/signing/ed25519_signer.py                     65      0   100%
beacon_core/signing/field_signing_keys.py                  5      0   100%
beacon_core/signing/kms_signer.py                         33      2    94%
beacon_core/telemetry/financial_engine.py                 63      6    90%
beacon_core/telemetry/financial_validator.py              36      1    97%
beacon_core/telemetry/survivability_engine.py             39      1    97%
beacon_core/telemetry/telemetry_exporter.py              113      3    97%
iam_substrate/ledger/audit_log.py                         23      0   100%
iam_substrate/substrate_api/autoheal.py                   69     15    78%
iam_substrate/substrate_api/database.py                   56     14    75%
iam_substrate/substrate_api/main.py                      324     18    94%
iam_substrate/substrate_api/models.py                     47      0   100%
iam_substrate/substrate_api/policy_engine.py             126     11    91%
iam_substrate/substrate_api/role_decay.py                151      7    95%
iam_substrate/substrate_api/scoring.py                    15      0   100%
iam_substrate/substrate_api/telemetry_emitter.py          14      0   100%
iam_substrate/webhooks/hmac_handler.py                    24      0   100%
identity_loop/feeds/farcaster_adapter.py                  27      0   100%
identity_loop/feeds/lens_adapter.py                       37      0   100%
identity_loop/feeds/rss_generator.py                      56      0   100%
identity_loop/well_known/signing_keys_publisher.py        24      0   100%
identity_loop/zenodo/ipfs_pinner.py                       25      0   100%
identity_loop/zenodo/zenodo_client.py                     27      0   100%
kcp/continuity_verifier.py                                36      0   100%
kcp/key_state.py                                          45      0   100%
kcp/rotation_handler.py                                   44      0   100%
----------------------------------------------------------------------
TOTAL                                                   2082    208    90%
425 passed in 17.86s
```
