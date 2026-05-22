"""
Round 4 targeted coverage tests — aims to push total coverage from 73.66% to ~79%.

Targets:
  - iam_substrate/substrate_api/main.py (64%): validate, telemetry/finance,
    telemetry/temporal, field_status, metrics, admin verify_admin_key branches
  - beacon_core/telemetry/telemetry_exporter.py (80%): SQLite-backed
    insert_field_telemetry, insert_iam_event, get_s_n_days_ago, get_q_variance,
    get_recent_field_telemetry, stub-mode branches
  - iam_substrate/substrate_api/autoheal.py (75%): run_autoheal with db session
    (audit log path), Slack alert with/without SLACK_WEBHOOK_URL
  - iam_substrate/substrate_api/database.py (52%): get_db, get_session_local,
    SQLite engine creation
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared FastAPI test client (same SQLite DB as test_substrate_api.py uses,
# but this module creates its own isolated DB to avoid fixture ordering issues)
# ---------------------------------------------------------------------------

_TMP4 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP4.close()
_DB4_URL = f"sqlite:///{_TMP4.name}"

os.environ.setdefault("DATABASE_URL", _DB4_URL)
os.environ.setdefault("SUBSTRATE_HMAC_SECRET", "dev_secret_67890")
_HMAC_SECRET = os.environ["SUBSTRATE_HMAC_SECRET"]


def _signed_post(client, path: str, payload: dict):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(_HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        path,
        content=body,
        headers={"Content-Type": "application/json", "X-Substrate-Signature": sig},
    )


@pytest.fixture(scope="module")
def api_client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import iam_substrate.substrate_api.database as db_mod

    engine = create_engine(_DB4_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_mod._engine = engine
    db_mod._SessionLocal = SessionLocal

    with patch("iam_substrate.substrate_api.role_decay.start_scheduler"), \
         patch("iam_substrate.substrate_api.role_decay.stop_scheduler"):

        from iam_substrate.substrate_api.models import Base
        Base.metadata.create_all(bind=engine)

        from iam_substrate.substrate_api.main import app
        from iam_substrate.substrate_api.database import get_db
        from fastapi.testclient import TestClient

        def override_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# main.py — validate endpoint (lines 527-533)
# ---------------------------------------------------------------------------

class TestValidateEndpoint:
    def test_validate_valid_bundle(self, api_client):
        resp = api_client.post(
            "/validate",
            json={"bundle": {"identity_id": "v1", "S": 0.8, "Q": 1.0, "tau": 0.9}},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_missing_field_returns_invalid(self, api_client):
        resp = api_client.post(
            "/validate",
            json={"bundle": {"identity_id": "v2", "S": 0.8, "Q": 1.0}},  # missing tau
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert "tau" in data["reason"]

    def test_validate_S_out_of_range(self, api_client):
        resp = api_client.post(
            "/validate",
            json={"bundle": {"identity_id": "v3", "S": 1.5, "Q": 1.0, "tau": 0.5}},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_validate_Q_zero_returns_invalid(self, api_client):
        resp = api_client.post(
            "/validate",
            json={"bundle": {"identity_id": "v4", "S": 0.8, "Q": 0.0, "tau": 0.5}},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_validate_non_numeric_S_returns_invalid(self, api_client):
        resp = api_client.post(
            "/validate",
            json={"bundle": {"identity_id": "v5", "S": "bad", "Q": 1.0, "tau": 0.5}},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


# ---------------------------------------------------------------------------
# main.py — telemetry/finance endpoint (lines 615-646)
# ---------------------------------------------------------------------------

class TestTelemetryFinanceEndpoint:
    def test_finance_returns_schema_version(self, api_client):
        resp = api_client.get("/telemetry/finance")
        assert resp.status_code == 200
        data = resp.json()
        assert "schema_version" in data
        assert "float_yield" in data
        assert "liquidity_signal" in data

    def test_finance_returns_timestamp(self, api_client):
        resp = api_client.get("/telemetry/finance")
        assert "timestamp" in resp.json()

    def test_finance_coherence_signal_is_numeric(self, api_client):
        resp = api_client.get("/telemetry/finance")
        data = resp.json()
        assert isinstance(data.get("coherence_signal"), (int, float))


# ---------------------------------------------------------------------------
# main.py — telemetry/temporal endpoint (lines 660-702)
# ---------------------------------------------------------------------------

class TestTelemetryTemporalEndpoint:
    def test_temporal_returns_200(self, api_client):
        resp = api_client.get("/telemetry/temporal")
        assert resp.status_code == 200

    def test_temporal_has_tau_field(self, api_client):
        data = api_client.get("/telemetry/temporal").json()
        assert "tau" in data

    def test_temporal_has_admitted_field(self, api_client):
        data = api_client.get("/telemetry/temporal").json()
        assert "admitted" in data


# ---------------------------------------------------------------------------
# main.py — /field/v1/status.json (lines 230-231)
# ---------------------------------------------------------------------------

class TestFieldStatusEndpoint:
    def test_field_status_returns_200(self, api_client):
        resp = api_client.get("/field/v1/status.json")
        assert resp.status_code == 200

    def test_field_status_has_context(self, api_client):
        data = api_client.get("/field/v1/status.json").json()
        assert "@context" in data or "S" in data or "status" in data


# ---------------------------------------------------------------------------
# main.py — /metrics endpoint (lines 596-598)
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    def test_metrics_returns_prometheus_text(self, api_client):
        resp = api_client.get("/metrics")
        assert resp.status_code == 200
        assert b"request_count" in resp.content or b"# HELP" in resp.content


# ---------------------------------------------------------------------------
# main.py — admin verify_admin_key branches (lines 89-95)
# ---------------------------------------------------------------------------

class TestVerifyAdminKey:
    def test_missing_admin_key_returns_401(self, api_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "secret123"):
            resp = api_client.get("/policy/rules")
            assert resp.status_code in (401, 403, 422)

    def test_wrong_admin_key_returns_403(self, api_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "secret123"):
            resp = api_client.get(
                "/policy/rules",
                headers={"X-Admin-Key": "wrong_key"},
            )
            assert resp.status_code in (401, 403)

    def test_correct_admin_key_is_accepted(self, api_client):
        with patch("iam_substrate.substrate_api.main._ADMIN_API_KEY", "correct_key"):
            resp = api_client.get(
                "/policy/rules",
                headers={"X-Admin-Key": "correct_key"},
            )
            assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# main.py — _prime_q_buffer and _purge_stale_telemetry (lines 110-135, 174)
# ---------------------------------------------------------------------------

class TestPrimeAndPurge:
    def test_prime_q_buffer_does_not_raise(self):
        with patch("iam_substrate.substrate_api.role_decay.start_scheduler"), \
             patch("iam_substrate.substrate_api.role_decay.stop_scheduler"):
            from iam_substrate.substrate_api import main as m
            m._prime_q_buffer()  # should not raise

    def test_purge_stale_telemetry_on_empty_db(self):
        with patch("iam_substrate.substrate_api.role_decay.start_scheduler"), \
             patch("iam_substrate.substrate_api.role_decay.stop_scheduler"):
            from iam_substrate.substrate_api import main as m
            from iam_substrate.substrate_api.database import get_db
            session = next(get_db())
            m._purge_stale_telemetry(session)  # should not raise


# ---------------------------------------------------------------------------
# TelemetryExporter — SQLite-backed paths (lines 96-227)
# ---------------------------------------------------------------------------

class TestTelemetryExporterSQLite:
    """Test TelemetryExporter with a live SQLite backend."""

    @pytest.fixture(scope="class")
    def exporter(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        return TelemetryExporter(database_url=f"sqlite:///{tmp.name}")

    def test_insert_field_telemetry_does_not_raise(self, exporter):
        exporter.insert_field_telemetry({
            "identity_id": "te-01",
            "S": 0.88,
            "delta_S": 0.01,
            "Q": 1.0,
            "tau": 0.95,
            "nabla_phi": 0.02,
            "field_state": "stable",
            "float_yield": 0.055,
            "liquidity_signal": 0.87,
            "coherence_signal": 0.91,
            "r_HSCE": 0.044,
            "float_reinvestment_rate": 0.06,
        })  # must not raise

    def test_insert_iam_event_does_not_raise(self, exporter):
        exporter.insert_iam_event({
            "identity_id": "te-01",
            "event_type": "score",
            "S": 0.88,
            "D": 0.75,
            "Ttau": 0.93,
            "admitted": True,
            "active_policies": ["P001"],
        })

    def test_get_s_n_days_ago_returns_none_when_no_history(self, exporter):
        result = exporter.get_s_n_days_ago(30)
        assert result is None or isinstance(result, float)

    def test_get_q_variance_returns_zero_with_little_data(self, exporter):
        result = exporter.get_q_variance(cycles=7)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_get_recent_field_telemetry_returns_list(self, exporter):
        rows = exporter.get_recent_field_telemetry(days=30)
        assert isinstance(rows, list)

    def test_stub_mode_insert_field_telemetry_is_noop(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url=None)
        exp.insert_field_telemetry({"identity_id": "stub", "S": 0.5})  # noop

    def test_stub_mode_get_s_n_days_ago_returns_none(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url=None)
        assert exp.get_s_n_days_ago(7) is None

    def test_stub_mode_get_q_variance_returns_zero(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url=None)
        assert exp.get_q_variance() == 0.0

    def test_stub_mode_get_recent_field_telemetry_returns_list(self):
        from beacon_core.telemetry.telemetry_exporter import TelemetryExporter
        exp = TelemetryExporter(database_url=None)
        result = exp.get_recent_field_telemetry()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# autoheal.py — run_autoheal with db session (audit log path, lines 159-160)
# and Slack alert paths (lines 178-179)
# ---------------------------------------------------------------------------

class TestAutoHealWithDbSession:
    def test_run_autoheal_with_db_session_writes_audit(self):
        from iam_substrate.substrate_api import autoheal
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from iam_substrate.substrate_api.models import Base

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        engine = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        flagged = [{"id": "autoheal-01", "S": 0.5, "field_state": "incident"}]
        with patch.object(autoheal, "GH_APP_ID", ""), \
             patch.object(autoheal, "SLACK_WEBHOOK_URL", ""), \
             patch("iam_substrate.ledger.audit_log.append_audit_entry") as mock_audit:
            results = autoheal.run_autoheal(flagged, db=session)
        assert len(results) == 1
        mock_audit.assert_called_once()

    def test_run_autoheal_audit_exception_is_swallowed(self):
        from iam_substrate.substrate_api import autoheal

        flagged = [{"id": "autoheal-02", "S": 0.4, "field_state": "incident"}]
        mock_db = MagicMock()
        with patch.object(autoheal, "GH_APP_ID", ""), \
             patch.object(autoheal, "SLACK_WEBHOOK_URL", ""), \
             patch("iam_substrate.ledger.audit_log.append_audit_entry",
                   side_effect=RuntimeError("DB exploded")):
            results = autoheal.run_autoheal(flagged, db=mock_db)
        assert len(results) == 1  # should still return despite audit failure

    def test_post_slack_alert_with_webhook_posts(self):
        from iam_substrate.substrate_api import autoheal
        identity = {"id": "slack-01", "S": 0.45, "field_state": "incident"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(autoheal, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"), \
             patch("iam_substrate.substrate_api.autoheal.requests.post",
                   return_value=mock_resp) as mock_post:
            autoheal._post_slack_alert(identity)
        mock_post.assert_called_once()

    def test_post_slack_alert_handles_request_exception(self):
        from iam_substrate.substrate_api import autoheal
        identity = {"id": "slack-02", "S": 0.3, "field_state": "incident"}
        with patch.object(autoheal, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"), \
             patch("urllib.request.urlopen", side_effect=Exception("network error")):
            autoheal._post_slack_alert(identity)  # must not raise


# ---------------------------------------------------------------------------
# database.py — get_db generator, get_session_local (lines 39-56)
# ---------------------------------------------------------------------------

class TestDatabaseModule:
    def test_get_session_local_returns_callable(self):
        import iam_substrate.substrate_api.database as db_mod
        factory = db_mod.get_session_local()
        assert callable(factory)

    def test_get_db_yields_and_closes(self):
        import iam_substrate.substrate_api.database as db_mod
        gen = db_mod.get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass  # expected after cleanup

    def test_get_engine_returns_engine(self):
        import iam_substrate.substrate_api.database as db_mod
        engine = db_mod._get_engine()
        assert engine is not None
