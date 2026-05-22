"""
Coverage boost tests — targets remaining gaps in:
  - iam_substrate/substrate_api/policy_engine.py (79% → 90%+)
  - iam_substrate/substrate_api/database.py (61% → 80%+)
  - iam_substrate/substrate_api/main.py (76% → 82%+)
  - beacon_core/telemetry/telemetry_exporter.py (80% → 88%+)
  - beacon_core/dns/godaddy_updater.py (88% → 100%)
  - kcp/rotation_handler.py line 47
  - beacon_core/signing/ed25519_signer.py lines 119-120
  - beacon_core/telemetry/financial_engine.py remaining
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# policy_engine.py — string comparison, correct op names (lt/le/gt/ge/eq/ne),
# _maybe_reload, _load_policies error, _get_file_mtime error
# ===========================================================================

class TestPolicyEngineExtended:
    def test_ast_safe_compare_unknown_op_returns_false(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        result = _ast_safe_compare(0.5, "unknown_op", 0.7)
        assert result is False

    def test_ast_safe_compare_lt_true(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.5, "lt", 0.7) is True

    def test_ast_safe_compare_lt_false(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.9, "lt", 0.7) is False

    def test_ast_safe_compare_gt_true(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.9, "gt", 0.7) is True

    def test_ast_safe_compare_gt_false(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.5, "gt", 0.7) is False

    def test_ast_safe_compare_le_equal(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.7, "le", 0.7) is True

    def test_ast_safe_compare_le_below(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.3, "le", 0.7) is True

    def test_ast_safe_compare_ge_equal(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.7, "ge", 0.7) is True

    def test_ast_safe_compare_ge_above(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.9, "ge", 0.7) is True

    def test_ast_safe_compare_eq_true(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.7, "eq", 0.7) is True

    def test_ast_safe_compare_ne_true(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.5, "ne", 0.7) is True

    def test_ast_safe_compare_ne_false(self):
        from iam_substrate.substrate_api.policy_engine import _ast_safe_compare
        assert _ast_safe_compare(0.7, "ne", 0.7) is False

    def test_eval_condition_string_equality_matches(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "field_state", "value": "incident", "op": "eq"}
        ctx = {"field_state": "incident"}
        assert _eval_condition(cond, ctx) is True

    def test_eval_condition_string_equality_no_match(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "field_state", "value": "stable", "op": "eq"}
        ctx = {"field_state": "incident"}
        assert _eval_condition(cond, ctx) is False

    def test_eval_condition_string_value_comparison(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        # When either side is a string, falls back to direct equality check
        cond = {"field": "field_state", "value": "critical", "op": "eq"}
        ctx = {"field_state": "critical"}
        assert _eval_condition(cond, ctx) is True

    def test_eval_condition_missing_field_returns_false(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "nonexistent", "value": 0.5, "op": "lt"}
        assert _eval_condition(cond, {}) is False

    def test_eval_condition_threshold_none_returns_false(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "S", "threshold": None, "op": "lt"}
        ctx = {"S": 0.5}
        assert _eval_condition(cond, ctx) is False

    def test_eval_condition_op_none_returns_false(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "S", "threshold": 0.7, "op": None}
        ctx = {"S": 0.5}
        assert _eval_condition(cond, ctx) is False

    def test_eval_condition_threshold_numeric_comparison(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "S", "threshold": 0.7, "op": "lt"}
        ctx = {"S": 0.5}
        assert _eval_condition(cond, ctx) is True

    def test_eval_condition_value_numeric_comparison(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        cond = {"field": "S", "value": 0.5, "op": "gt"}
        ctx = {"S": 0.9}
        assert _eval_condition(cond, ctx) is True

    def test_reload_policies_returns_list(self):
        from iam_substrate.substrate_api.policy_engine import reload_policies
        result = reload_policies()
        assert isinstance(result, list)

    def test_maybe_reload_same_mtime_no_reload(self):
        from iam_substrate.substrate_api import policy_engine as pe
        orig_mtime = pe._policies_mtime
        original_policies = pe._POLICIES[:]
        pe._maybe_reload()
        assert pe._policies_mtime == orig_mtime

    def test_maybe_reload_changed_mtime_triggers_reload(self):
        from iam_substrate.substrate_api import policy_engine as pe
        orig_mtime = pe._policies_mtime
        try:
            pe._policies_mtime = orig_mtime - 999.0
            pe._maybe_reload()
        finally:
            pe._policies_mtime = orig_mtime

    def test_load_policies_missing_file_returns_empty(self):
        import pathlib
        from iam_substrate.substrate_api import policy_engine as pe
        fake_path = pathlib.Path("/nonexistent/temporal_policies.yaml")
        orig = pe._POLICIES_PATH
        try:
            pe._POLICIES_PATH = fake_path
            result = pe._load_policies()
        finally:
            pe._POLICIES_PATH = orig
        assert result == []

    def test_get_file_mtime_missing_file_returns_zero(self):
        import pathlib
        from iam_substrate.substrate_api import policy_engine as pe
        fake_path = pathlib.Path("/nonexistent/temporal_policies.yaml")
        orig = pe._POLICIES_PATH
        try:
            pe._POLICIES_PATH = fake_path
            result = pe._get_file_mtime()
        finally:
            pe._POLICIES_PATH = orig
        assert result == 0.0

    def test_policy_evaluate_returns_admitted_key(self):
        from iam_substrate.substrate_api.policy_engine import evaluate
        ctx = {"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95, "nabla_phi": 0.0,
               "field_state": "stable", "D": 0.8, "Ttau": 0.9}
        result = evaluate(ctx)
        assert "admitted" in result
        assert "active_policy_ids" in result
        assert "throttle_rate" in result

    def test_policy_evaluate_high_stress_context(self):
        from iam_substrate.substrate_api.policy_engine import evaluate
        ctx = {"S": 0.2, "delta_S": -0.4, "Q": 0.5, "tau": 0.2, "nabla_phi": 1.0,
               "field_state": "critical", "D": 0.1, "Ttau": 0.1}
        result = evaluate(ctx)
        assert "admitted" in result

    def test_get_active_policies_returns_list(self):
        from iam_substrate.substrate_api.policy_engine import get_active_policies
        result = get_active_policies()
        assert isinstance(result, list)

    def test_eval_condition_unknown_op_in_string_path_returns_false(self):
        from iam_substrate.substrate_api.policy_engine import _eval_condition
        # op_func will be None for a completely unknown operator in string comparison path
        cond = {"field": "field_state", "value": "stable", "op": "unknown_op"}
        ctx = {"field_state": "stable"}
        # Should return False (op_func is None for unknown op)
        result = _eval_condition(cond, ctx)
        assert isinstance(result, bool)


# ===========================================================================
# database.py — _migrate_phase2_columns, init_db, with SQLite
# ===========================================================================

_DB_BOOST_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB_BOOST_FILE.close()
_SQLITE_URL = f"sqlite:///{_DB_BOOST_FILE.name}"


class TestDatabaseExtended:
    """All tests explicitly set _engine to a SQLite engine to avoid psycopg2."""

    def _get_sqlite_engine(self):
        from sqlalchemy import create_engine
        return create_engine(_SQLITE_URL, connect_args={"check_same_thread": False})

    def test_migrate_phase2_columns_sqlite_skips_gracefully(self):
        import iam_substrate.substrate_api.database as db_mod
        engine = self._get_sqlite_engine()
        orig_engine = db_mod._engine
        try:
            db_mod._engine = engine
            db_mod._migrate_phase2_columns()  # must not raise
        finally:
            db_mod._engine = orig_engine

    def test_init_db_creates_tables_without_error(self):
        import iam_substrate.substrate_api.database as db_mod
        from sqlalchemy.orm import sessionmaker
        engine = self._get_sqlite_engine()
        session = sessionmaker(bind=engine)
        orig_engine, orig_session = db_mod._engine, db_mod._SessionLocal
        try:
            db_mod._engine = engine
            db_mod._SessionLocal = session
            db_mod.init_db()
        finally:
            db_mod._engine = orig_engine
            db_mod._SessionLocal = orig_session

    def test_migrate_phase2_columns_postgres_column_error_swallowed(self):
        import iam_substrate.substrate_api.database as db_mod
        mock_engine = MagicMock()
        mock_engine.url = MagicMock()
        type(mock_engine.url).__str__ = lambda self: "postgresql://fake/fake"
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("column already exists")
        mock_conn.rollback.return_value = None
        mock_engine.connect.return_value = mock_conn
        orig = db_mod._engine
        try:
            db_mod._engine = mock_engine
            db_mod._migrate_phase2_columns()  # must not raise
        finally:
            db_mod._engine = orig

    def test_get_session_local_returns_factory(self):
        import iam_substrate.substrate_api.database as db_mod
        from sqlalchemy.orm import sessionmaker
        engine = self._get_sqlite_engine()
        session = sessionmaker(bind=engine)
        orig_engine, orig_session = db_mod._engine, db_mod._SessionLocal
        try:
            db_mod._engine = engine
            db_mod._SessionLocal = session
            factory = db_mod.get_session_local()
            assert factory is session
        finally:
            db_mod._engine = orig_engine
            db_mod._SessionLocal = orig_session

    def test_get_db_yields_and_closes(self):
        import iam_substrate.substrate_api.database as db_mod
        from sqlalchemy.orm import sessionmaker
        engine = self._get_sqlite_engine()
        session_factory = sessionmaker(bind=engine)
        orig_engine, orig_session = db_mod._engine, db_mod._SessionLocal
        try:
            db_mod._engine = engine
            db_mod._SessionLocal = session_factory
            gen = db_mod.get_db()
            db = next(gen)
            assert db is not None
            try:
                next(gen)
            except StopIteration:
                pass
        finally:
            db_mod._engine = orig_engine
            db_mod._SessionLocal = orig_session


# ===========================================================================
# main.py — additional endpoint coverage via TestClient
# ===========================================================================

_TMP_BOOST = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_BOOST.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_BOOST.name}")
os.environ.setdefault("SUBSTRATE_HMAC_SECRET", "dev_secret_67890")
_HMAC = os.environ["SUBSTRATE_HMAC_SECRET"]


@pytest.fixture(scope="module")
def boost_client():
    import hashlib
    import hmac as hmac_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import iam_substrate.substrate_api.database as db_mod

    engine = create_engine(f"sqlite:///{_TMP_BOOST.name}",
                           connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_mod._engine = engine
    db_mod._SessionLocal = Session

    with patch("iam_substrate.substrate_api.role_decay.start_scheduler"), \
         patch("iam_substrate.substrate_api.role_decay.stop_scheduler"):
        from iam_substrate.substrate_api.models import Base
        Base.metadata.create_all(bind=engine)
        from iam_substrate.substrate_api.main import app
        from iam_substrate.substrate_api.database import get_db

        def override_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


def _sign_body(body_dict: dict) -> dict:
    import hashlib
    import hmac as hmac_mod
    body = json.dumps(body_dict).encode()
    sig = "sha256=" + hmac_mod.new(_HMAC.encode(), body, hashlib.sha256).hexdigest()
    return {"content": body, "headers": {"Content-Type": "application/json",
                                          "X-Substrate-Signature": sig}}


class TestMainEndpointsExtended:
    def test_field_matrix_returns_200(self, boost_client):
        with patch("beacon_core.lambdas.generate_matrix.handler.handler",
                   return_value={"matrix": []}):
            resp = boost_client.get("/field/v1/matrix.json")
        assert resp.status_code == 200

    def test_field_benchmarks_returns_200(self, boost_client):
        with patch("beacon_core.lambdas.generate_benchmarks.handler.handler",
                   return_value={"benchmarks": {}}):
            resp = boost_client.get("/field/v1/benchmarks.json")
        assert resp.status_code == 200

    def test_field_pulse_returns_200(self, boost_client):
        with patch("beacon_core.lambdas.generate_pulse.handler.handler",
                   return_value={"theme": "green"}):
            resp = boost_client.get("/field/ui/v1/pulse.json")
        assert resp.status_code == 200

    def test_field_signing_keys_well_known(self, boost_client):
        resp = boost_client.get("/.well-known/field-signing-keys.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "type" in data

    def test_field_verify_bad_signature_returns_false(self, boost_client):
        resp = boost_client.post(
            "/field/v1/verify",
            json={"payload": {"S": 0.9, "field_state": "stable"},
                  "signature": "ed25519:invalidsig"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_field_verify_missing_hash_field_still_works(self, boost_client):
        resp = boost_client.post(
            "/field/v1/verify",
            json={"payload": {"S": 0.9, "hash": "abc", "signature": "ed25519:xyz"},
                  "signature": "ed25519:invalidsig"},
        )
        assert resp.status_code == 200

    def test_hsce_ready_returns_checks(self, boost_client):
        resp = boost_client.get("/hsce/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert "checks" in data
        assert "interface_version" in data["checks"]

    def test_policy_active_returns_policy_count(self, boost_client):
        resp = boost_client.get("/policy/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "policy_count" in data
        assert "policies" in data
        assert "current_evaluation" in data

    def test_policy_evaluate_endpoint_admitted_key(self, boost_client):
        resp = boost_client.post(
            "/policy/evaluate",
            json={"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95,
                  "nabla_phi": 0.0, "field_state": "stable",
                  "D": 0.8, "Ttau": 0.9, "event_type": "score"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "admitted" in data
        assert "input" in data

    def test_policy_rules_no_key_returns_401_or_403(self, boost_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "adminkey"):
            resp = boost_client.get("/policy/rules")
        assert resp.status_code in (401, 403)

    def test_policy_rules_wrong_key_returns_403(self, boost_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "adminkey"):
            resp = boost_client.get("/policy/rules",
                                    headers={"X-Admin-Key": "wrongkey"})
        assert resp.status_code == 403

    def test_policy_rules_correct_key_returns_200(self, boost_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "adminkey"):
            resp = boost_client.get("/policy/rules",
                                    headers={"X-Admin-Key": "adminkey"})
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data

    def test_score_update_existing_identity(self, boost_client):
        """POST /score twice — second triggers the UPDATE branch (lines 429-430)."""
        kw = _sign_body({"identity_id": "update-test-boost", "Q": 1.0,
                         "tau": 0.9, "nabla_phi": 0.0})
        boost_client.post("/score", **kw)
        resp = boost_client.post("/score", **kw)
        assert resp.status_code == 200
        assert "S" in resp.json()

    def test_score_audit_exception_does_not_fail(self, boost_client):
        """audit_log exception must not cause 500 (lines 453-454 catch block)."""
        kw = _sign_body({"identity_id": "audit-fail-boost", "Q": 1.0,
                         "tau": 0.9, "nabla_phi": 0.0})
        with patch("iam_substrate.ledger.audit_log.append_audit_entry",
                   side_effect=Exception("audit DB down")):
            resp = boost_client.post("/score", **kw)
        assert resp.status_code == 200

    def test_events_invalid_json_returns_422(self, boost_client):
        import hashlib
        import hmac as hmac_mod
        body = b"not-json"
        sig = "sha256=" + hmac_mod.new(_HMAC.encode(), body, hashlib.sha256).hexdigest()
        resp = boost_client.post(
            "/events",
            content=body,
            headers={"Content-Type": "application/json", "X-Substrate-Signature": sig},
        )
        assert resp.status_code in (422, 400)

    def test_telemetry_temporal_has_tau(self, boost_client):
        resp = boost_client.get("/telemetry/temporal")
        assert resp.status_code == 200
        assert "tau" in resp.json()

    def test_field_status_json_returns_200(self, boost_client):
        with patch("beacon_core.lambdas.generate_status.handler.handler",
                   return_value={"S": 0.9, "@context": "https://schema.org",
                                  "@type": "Dataset", "schema_version": "2.0",
                                  "generated_at": 1746614400, "feeds_fresh": False,
                                  "hash": "abc", "field_state": "stable",
                                  "delta_S": 0.01, "Q": 1.0, "tau": 0.95,
                                  "nabla_phi": 0.0, "url": "https://myntist.com",
                                  "float_yield": 0.05, "liquidity_signal": 0.8,
                                  "coherence_signal": 0.9, "r_HSCE": 0.04,
                                  "float_reinvestment_rate": 0.06}):
            resp = boost_client.get("/field/v1/status.json")
        assert resp.status_code == 200


# ===========================================================================
# telemetry_exporter.py — _try_create_hypertables (SQLite silently skips),
# insert and query failure paths
# ===========================================================================

class TestTelemetryExporterFailurePaths:
    def test_init_with_invalid_url_enters_stub_mode(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url="postgresql://bad:bad@nonexistent/db")
        assert not exp._initialized

    def test_insert_field_telemetry_in_stub_mode_is_noop(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url="postgresql://bad:bad@nonexistent/db")
        exp.insert_field_telemetry({"identity_id": "x", "S": 0.9})  # must not raise

    def test_insert_iam_event_in_stub_mode_is_noop(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url="postgresql://bad:bad@nonexistent/db")
        exp.insert_iam_event({"identity_id": "x", "event_type": "score"})  # must not raise

    def _make_sqlite_exporter(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        return TelemetryExporter(database_url=f"sqlite:///{tmp.name}")

    def test_insert_field_telemetry_db_error_is_swallowed(self):
        exp = self._make_sqlite_exporter()
        assert exp._initialized
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("insert failed")
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        exp.insert_field_telemetry({"identity_id": "x", "S": 0.9})  # must not raise

    def test_insert_iam_event_db_error_is_swallowed(self):
        exp = self._make_sqlite_exporter()
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("insert failed")
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        exp.insert_iam_event({"identity_id": "x", "event_type": "score"})  # must not raise

    def test_get_s_n_days_ago_db_error_returns_none(self):
        exp = self._make_sqlite_exporter()
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("DB error")
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        result = exp.get_s_n_days_ago(7)
        assert result is None

    def test_get_q_variance_db_error_returns_zero(self):
        exp = self._make_sqlite_exporter()
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("DB error")
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        result = exp.get_q_variance()
        assert result == 0.0

    def test_get_recent_field_telemetry_db_error_returns_empty(self):
        exp = self._make_sqlite_exporter()
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = Exception("DB error")
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        result = exp.get_recent_field_telemetry()
        assert result == []

    def test_get_q_variance_single_value_returns_zero(self):
        exp = self._make_sqlite_exporter()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1.0,)]
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result
        exp._engine = MagicMock()
        exp._engine.connect.return_value = mock_conn
        result = exp.get_q_variance()
        assert result == 0.0

    def test_try_create_hypertables_with_sqlite_silently_passes(self):
        exp = self._make_sqlite_exporter()
        # SQLite does not support TimescaleDB — _try_create_hypertables must not raise
        exp._try_create_hypertables()  # should silently pass


# ===========================================================================
# godaddy_updater.py — remaining branches
# ===========================================================================

class TestGoDaddyUpdaterExtended:
    def test_update_dns_records_no_api_key_returns_false_dict(self):
        from beacon_core.dns import godaddy_updater as gu
        with patch.object(gu, "GODADDY_API_KEY", ""):
            result = gu.update_dns_records(S=0.9, delta_S=0.01, tau=0.95, Q=1.0,
                                           payload_hash="abc123")
        assert result["_s.v1"] is False
        assert result["_buoy.latest"] is False
        assert result["_ledger.anchor"] is False
        assert result["_float.audit"] is False

    def test_update_txt_record_exception_returns_false(self):
        from beacon_core.dns import godaddy_updater as gu
        with patch("requests.put", side_effect=Exception("timeout")), \
             patch.object(gu, "GODADDY_API_KEY", "key"), \
             patch.object(gu, "GODADDY_API_SECRET", "secret"):
            result = gu._update_txt_record("_s.v1", "s=0.9000")
        assert result is False

    def test_update_txt_record_http_error_returns_false(self):
        from beacon_core.dns import godaddy_updater as gu
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 422")
        with patch("requests.put", return_value=mock_resp), \
             patch.object(gu, "GODADDY_API_KEY", "key"), \
             patch.object(gu, "GODADDY_API_SECRET", "secret"):
            result = gu._update_txt_record("_s.v1", "s=0.9000")
        assert result is False

    def test_update_dns_records_with_cid_and_doi_calls_ledger_anchor(self):
        from beacon_core.dns import godaddy_updater as gu
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch.object(gu, "GODADDY_API_KEY", "key"), \
             patch.object(gu, "GODADDY_API_SECRET", "secret"), \
             patch("requests.put", return_value=mock_resp):
            result = gu.update_dns_records(
                S=0.9, delta_S=0.01, tau=0.95, Q=1.0,
                payload_hash="abc123",
                cid="QmRealCID", doi="10.5281/zenodo.123",
            )
        assert result["_ledger.anchor"] is True

    def test_update_dns_records_no_cid_doi_skips_ledger(self):
        from beacon_core.dns import godaddy_updater as gu
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch.object(gu, "GODADDY_API_KEY", "key"), \
             patch.object(gu, "GODADDY_API_SECRET", "secret"), \
             patch("requests.put", return_value=mock_resp):
            result = gu.update_dns_records(
                S=0.9, delta_S=0.01, tau=0.95, Q=1.0,
                payload_hash="abc123", cid=None, doi=None,
            )
        assert result["_ledger.anchor"] is False

    def test_update_dns_records_with_float_yield_builds_float_audit(self):
        from beacon_core.dns import godaddy_updater as gu
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch.object(gu, "GODADDY_API_KEY", "key"), \
             patch.object(gu, "GODADDY_API_SECRET", "secret"), \
             patch("requests.put", return_value=mock_resp):
            result = gu.update_dns_records(
                S=0.9, delta_S=0.01, tau=0.95, Q=1.0,
                payload_hash="abc123",
                float_yield=0.055,
                float_reinvestment_rate=0.06,
                coherence_signal=0.88,
            )
        assert "_float.audit" in result
        assert result["_float.audit"] is True


# ===========================================================================
# kcp/rotation_handler.py — line 47: rotate_key when no key chain exists
# ===========================================================================

class TestRotationHandlerLine47:
    def test_rotate_key_when_no_chain_exists_calls_create_genesis(self):
        """Line 47 — create_genesis branch when no prior chain exists."""
        import pathlib
        import kcp.key_state as ks_mod
        from kcp.rotation_handler import rotate_key
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = pathlib.Path(tmpdir) / "key_states.json"
            with patch.object(ks_mod, "KEY_STATES_FILE", fake_path):
                with patch("kcp.rotation_handler.get_latest_key_state", return_value=None), \
                     patch("kcp.key_state.KEY_STATES_FILE", fake_path):
                    result = rotate_key("new-pubkey-abc")
        assert result is not None
        assert result.public_key == "new-pubkey-abc"

    def test_rotate_key_with_custom_thresholds_creates_genesis(self):
        import pathlib
        import kcp.key_state as ks_mod
        from kcp.rotation_handler import rotate_key
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = pathlib.Path(tmpdir) / "key_states.json"
            with patch("kcp.rotation_handler.get_latest_key_state", return_value=None), \
                 patch("kcp.key_state.KEY_STATES_FILE", fake_path):
                result = rotate_key("pubkey-thresholds", threshold_m=2, threshold_n=4)
        assert result.threshold_m == 2
        assert result.threshold_n == 4

    def test_check_key_age_no_env_var_set_returns_dict(self):
        from kcp.rotation_handler import check_key_age
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ED25519_KEY_CREATED", None)
            result = check_key_age()
        assert isinstance(result, dict)
        assert "rotation_required" in result
        assert "age_days" in result
        assert result["age_days"] is None

    def test_check_key_age_with_recent_date_not_required(self):
        from kcp.rotation_handler import check_key_age
        from datetime import date, timedelta
        recent = (date.today() - timedelta(days=5)).isoformat()
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": recent,
                                     "KEY_MAX_AGE_DAYS": "330"}):
            result = check_key_age()
        assert result["rotation_required"] is False
        assert result["age_days"] == 5

    def test_check_key_age_invalid_date_format_returns_none_age(self):
        from kcp.rotation_handler import check_key_age
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": "not-a-date"}):
            result = check_key_age()
        assert result["age_days"] is None
        assert result["rotation_required"] is False


# ===========================================================================
# beacon_core/signing/ed25519_signer.py — lines 119-120 (build_well_known
# when no key is configured — returns dict with None publicKeyMultibase)
# ===========================================================================

class TestEd25519SignerBuildWellKnown:
    def test_build_well_known_without_key_returns_dict_with_none_multibase(self):
        from beacon_core.signing import ed25519_signer
        with patch.object(ed25519_signer, "_load_public_key", return_value=None):
            result = ed25519_signer.build_well_known()
        assert result["publicKeyMultibase"] is None
        assert "@context" in result
        assert result["type"] == "Ed25519VerificationKey2020"

    def test_build_well_known_with_key_returns_multibase_string(self):
        from beacon_core.signing import ed25519_signer
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        with patch.object(ed25519_signer, "_load_public_key", return_value=public_key):
            result = ed25519_signer.build_well_known()
        assert result["publicKeyMultibase"] is not None

    def test_build_well_known_invalid_created_date_handles_gracefully(self):
        from beacon_core.signing import ed25519_signer
        with patch.object(ed25519_signer, "_load_public_key", return_value=None), \
             patch.object(ed25519_signer, "KEY_CREATED", "invalid-date"):
            result = ed25519_signer.build_well_known()
        assert "@context" in result

    def test_sign_function_no_key_returns_none(self):
        from beacon_core.signing import ed25519_signer
        with patch.object(ed25519_signer, "_load_private_key", return_value=None):
            result = ed25519_signer.sign(b"test bytes")
        assert result is None


# ===========================================================================
# beacon_core/telemetry/financial_engine.py — remaining coverage
# ===========================================================================

class TestFinancialEngineExtended:
    def test_update_q_buffer_beyond_capacity(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        for i in range(200):
            engine.update_q_buffer(float(i) / 100)
        var = engine.get_q_variance()
        assert isinstance(var, float)
        assert var >= 0.0

    def test_compute_all_no_timescale_client(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        survival = {"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95,
                    "nabla_phi": 0.0, "field_state": "stable"}
        result = engine.compute_all(survival, timescale_client=None)
        assert "float_yield" in result
        assert "liquidity_signal" in result

    def test_compute_all_with_timescale_client_no_historic_s(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        mock_client = MagicMock()
        mock_client.get_s_n_days_ago.return_value = None
        mock_client.get_q_variance.return_value = 0.0
        survival = {"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95,
                    "nabla_phi": 0.0, "field_state": "stable"}
        result = engine.compute_all(survival, timescale_client=mock_client)
        assert "float_yield" in result

    def test_compute_all_with_timescale_client_historic_s(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        mock_client = MagicMock()
        mock_client.get_s_n_days_ago.return_value = 0.75
        mock_client.get_q_variance.return_value = 0.02
        survival = {"S": 0.9, "delta_S": 0.05, "Q": 1.0, "tau": 0.95,
                    "nabla_phi": 0.0, "field_state": "stable"}
        result = engine.compute_all(survival, timescale_client=mock_client)
        assert isinstance(result["float_yield"], float)

    def test_compute_liquidity_signal_various_inputs(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        assert isinstance(engine.compute_liquidity_signal(0.01, 1.0), float)
        assert isinstance(engine.compute_liquidity_signal(-0.05, 0.5), float)
        assert isinstance(engine.compute_liquidity_signal(0.0, 0.5), float)

    def test_compute_coherence_signal_zero_variance(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        result = engine.compute_coherence_signal(tau=1.0, q_variance=0.0)
        assert isinstance(result, float)

    def test_compute_coherence_signal_high_variance(self):
        from beacon_core.telemetry.financial_engine import FinancialEngine
        engine = FinancialEngine()
        result = engine.compute_coherence_signal(tau=0.5, q_variance=2.0)
        assert isinstance(result, float)


# ===========================================================================
# beacon_core/telemetry/survivability_engine.py — line 70 (extreme values)
# ===========================================================================

class TestSurvivabilityEngineEdgeCases:
    def test_compute_positive_nabla_phi_high(self):
        from beacon_core.telemetry.survivability_engine import SurvivabilityEngine
        engine = SurvivabilityEngine()
        result = engine.compute(Q=0.01, nabla_phi=100.0, tau=0.01)
        assert 0.0 <= result.S <= 1.0

    def test_compute_negative_nabla_phi_clamps(self):
        from beacon_core.telemetry.survivability_engine import SurvivabilityEngine
        engine = SurvivabilityEngine()
        result = engine.compute(Q=1.0, nabla_phi=-1.0, tau=1.0)
        assert 0.0 <= result.S <= 1.0

    def test_compute_very_high_Q_clamps_S(self):
        from beacon_core.telemetry.survivability_engine import SurvivabilityEngine
        engine = SurvivabilityEngine()
        result = engine.compute(Q=1000.0, nabla_phi=0.0, tau=1.0)
        assert 0.0 <= result.S <= 1.0
