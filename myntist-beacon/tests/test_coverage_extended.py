"""
Extended coverage tests — round 3.

Covers previously uncovered lines in:
  - beacon_core/hsce/interface_contract.py  (push_to_hsce with endpoint, retry on timeout)
  - beacon_core/signing/ed25519_signer.py   (sign/verify paths, build_well_known)
  - iam_substrate/substrate_api/role_decay.py (check_and_heal, start/stop_scheduler,
                                               prune_telemetry, run_float_ledger,
                                               run_parquet_export)
  - iam_substrate/substrate_api/autoheal.py  (_open_github_pr skipped path)
"""
from __future__ import annotations

import base64
import binascii
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── beacon_core/hsce/interface_contract.py ───────────────────────────────────


class TestHSCEPushWithEndpoint:
    """Tests for push_to_hsce when HSCE_ENDPOINT is configured."""

    def _valid_payload(self):
        return {
            "schema_version": "2",
            "generated_at": 1700000000,
            "S": 0.9,
            "delta_S": 0.01,
            "Q": 1.0,
            "tau": 0.8,
            "nabla_phi": 0.1,
            "field_state": "stable",
            "float_yield": 0.05,
            "liquidity_signal": 0.7,
            "coherence_signal": 0.8,
            "r_HSCE": None,
            "float_reinvestment_rate": 0.9,
        }

    def test_push_with_endpoint_posts_successfully(self):
        """When HSCE_ENDPOINT is set and request succeeds, returns without error."""
        import importlib
        import beacon_core.hsce.interface_contract as hsce

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None

        with patch.dict(os.environ, {"HSCE_ENDPOINT": "https://hsce.example.com/push"}):
            importlib.reload(hsce)
            with patch("requests.post", return_value=mock_resp) as mock_post:
                hsce.push_to_hsce(self._valid_payload())
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "Content-Type" in call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))

        os.environ.pop("HSCE_ENDPOINT", None)
        importlib.reload(hsce)

    def test_push_with_token_sends_authorization_header(self):
        """When HSCE_API_TOKEN is set, Authorization: Bearer header is sent."""
        import importlib
        import beacon_core.hsce.interface_contract as hsce

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None

        with patch.dict(os.environ, {
            "HSCE_ENDPOINT": "https://hsce.example.com/push",
            "HSCE_API_TOKEN": "my-secret-token",
        }):
            importlib.reload(hsce)
            with patch("requests.post", return_value=mock_resp) as mock_post:
                hsce.push_to_hsce(self._valid_payload())
            sent_headers = mock_post.call_args.kwargs.get("headers", {})
            assert sent_headers.get("Authorization") == "Bearer my-secret-token"

        for k in ("HSCE_ENDPOINT", "HSCE_API_TOKEN"):
            os.environ.pop(k, None)
        importlib.reload(hsce)

    def test_push_retries_once_on_timeout(self):
        """On first-attempt Timeout, the function retries exactly once."""
        import importlib
        import beacon_core.hsce.interface_contract as hsce
        import requests as req_mod

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None

        with patch.dict(os.environ, {"HSCE_ENDPOINT": "https://hsce.example.com/push"}):
            importlib.reload(hsce)
            with patch("requests.post", side_effect=[req_mod.exceptions.Timeout(), mock_resp]) as mock_post:
                hsce.push_to_hsce(self._valid_payload())
            assert mock_post.call_count == 2

        os.environ.pop("HSCE_ENDPOINT", None)
        importlib.reload(hsce)

    def test_push_gives_up_after_two_timeouts(self):
        """Two consecutive Timeouts cause function to give up without raising."""
        import importlib
        import beacon_core.hsce.interface_contract as hsce
        import requests as req_mod

        with patch.dict(os.environ, {"HSCE_ENDPOINT": "https://hsce.example.com/push"}):
            importlib.reload(hsce)
            with patch("requests.post", side_effect=[req_mod.exceptions.Timeout(), req_mod.exceptions.Timeout()]) as mock_post:
                hsce.push_to_hsce(self._valid_payload())  # must not raise
            assert mock_post.call_count == 2

        os.environ.pop("HSCE_ENDPOINT", None)
        importlib.reload(hsce)

    def test_push_handles_generic_exception(self):
        """Non-timeout exceptions are caught and logged without raising."""
        import importlib
        import beacon_core.hsce.interface_contract as hsce

        with patch.dict(os.environ, {"HSCE_ENDPOINT": "https://hsce.example.com/push"}):
            importlib.reload(hsce)
            with patch("requests.post", side_effect=RuntimeError("connection refused")):
                hsce.push_to_hsce(self._valid_payload())  # must not raise

        os.environ.pop("HSCE_ENDPOINT", None)
        importlib.reload(hsce)


# ── beacon_core/signing/ed25519_signer.py ────────────────────────────────────


def _make_hex_private_key() -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.generate()
    return binascii.hexlify(priv.private_bytes_raw()).decode()


class TestEd25519Signer:
    """Additional coverage for ed25519_signer paths."""

    def test_load_private_key_returns_key_when_hex_set(self):
        """_load_private_key returns an Ed25519PrivateKey when PRIVATE_KEY_HEX is valid."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            result = ed._load_private_key()
            assert result is not None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_load_private_key_returns_none_on_invalid_hex(self):
        """_load_private_key returns None when PRIVATE_KEY_HEX is malformed."""
        from beacon_core.signing import ed25519_signer as ed

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = "zz-not-valid-hex"
            result = ed._load_private_key()
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_load_public_key_returns_key_when_private_key_set(self):
        """_load_public_key derives public key from private key."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            pub = ed._load_public_key()
            assert pub is not None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_public_key_multibase_returns_z_prefixed_string(self):
        """_public_key_multibase returns a base58 string prefixed with 'z'."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            result = ed._public_key_multibase()
            assert result is not None
            assert result.startswith("z")
            assert len(result) > 10
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_public_key_multibase_returns_none_without_key(self):
        """_public_key_multibase returns None when no private key is set."""
        from beacon_core.signing import ed25519_signer as ed

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = ""
            result = ed._public_key_multibase()
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_sign_returns_none_when_no_key(self):
        """sign() returns None when PRIVATE_KEY_HEX is empty."""
        from beacon_core.signing import ed25519_signer as ed

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = ""
            result = ed.sign(b"payload")
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_verify_returns_false_without_key(self):
        """verify() returns False when no public key is configured."""
        from beacon_core.signing import ed25519_signer as ed

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = ""
            result = ed.verify(b"payload", "ed25519:fakesig")
            assert result is False
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_verify_returns_false_for_non_ed25519_prefix(self):
        """verify() returns False when signature prefix is not 'ed25519:'."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            result = ed.verify(b"payload", "hmac:invalidsig")
            assert result is False
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_build_well_known_with_key_has_public_key_multibase(self):
        """build_well_known() with a configured key includes publicKeyMultibase."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig_priv = ed.PRIVATE_KEY_HEX
        orig_created = ed.KEY_CREATED
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            ed.KEY_CREATED = "2026-01-01T00:00:00Z"
            doc = ed.build_well_known()
            assert "publicKeyMultibase" in doc
            assert doc["publicKeyMultibase"].startswith("z")
            assert doc["type"] == "Ed25519VerificationKey2020"
            assert "@context" in doc
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            ed.KEY_CREATED = orig_created

    def test_build_well_known_without_key_returns_pending_doc(self):
        """build_well_known() without a key returns a pending stub document."""
        from beacon_core.signing import ed25519_signer as ed

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = ""
            doc = ed.build_well_known()
            assert "@context" in doc
            # Should not have publicKeyMultibase since no key
            assert "publicKeyMultibase" not in doc or doc.get("publicKeyMultibase") is None
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_build_well_known_derives_expires_from_created(self):
        """build_well_known() sets 'expires' to 1 year after 'created'."""
        from beacon_core.signing import ed25519_signer as ed

        hex_key = _make_hex_private_key()
        orig_priv = ed.PRIVATE_KEY_HEX
        orig_created = ed.KEY_CREATED
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            ed.KEY_CREATED = "2026-01-01T00:00:00Z"
            doc = ed.build_well_known()
            assert doc.get("expires", "").startswith("2027")
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            ed.KEY_CREATED = orig_created


# ── iam_substrate/substrate_api/role_decay.py ────────────────────────────────


def _make_in_memory_session():
    """Create a SQLite in-memory session with the same ORM models."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from iam_substrate.substrate_api.models import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Session(engine), engine


class TestCheckAndHeal:
    """Tests for role_decay.check_and_heal() with in-memory DB."""

    def test_check_and_heal_no_identities_does_not_raise(self):
        """check_and_heal with empty DB runs without error."""
        from iam_substrate.substrate_api import role_decay

        session, _ = _make_in_memory_session()
        with patch("iam_substrate.substrate_api.database.get_session_local",
                   return_value=lambda: session):
            role_decay.check_and_heal()  # must not raise

    def test_check_and_heal_healthy_identities_not_flagged(self):
        """check_and_heal with S >= 0.7 identities does not call autoheal."""
        from iam_substrate.substrate_api import role_decay
        from iam_substrate.substrate_api.models import Identity

        session, _ = _make_in_memory_session()
        session.add(Identity(id="healthy-01", S=0.9, Q=1.0, tau=1.0, nabla_phi=0.0,
                             delta_S=0.0, field_state="stable"))
        session.commit()

        mock_autoheal = MagicMock(return_value=[])
        with patch("iam_substrate.substrate_api.database.get_session_local",
                   return_value=lambda: session), \
             patch("iam_substrate.substrate_api.autoheal.run_autoheal", mock_autoheal):
            role_decay.check_and_heal()
        mock_autoheal.assert_not_called()

    def test_check_and_heal_low_S_identity_triggers_autoheal(self):
        """check_and_heal with S < 0.7 identity calls run_autoheal."""
        from iam_substrate.substrate_api import role_decay
        from iam_substrate.substrate_api.models import Identity

        session, _ = _make_in_memory_session()
        session.add(Identity(id="sick-01", S=0.5, Q=1.0, tau=1.0, nabla_phi=0.0,
                             delta_S=0.0, field_state="incident"))
        session.commit()

        mock_autoheal = MagicMock(return_value=[{"identity_id": "sick-01"}])
        with patch("iam_substrate.substrate_api.database.get_session_local",
                   return_value=lambda: session), \
             patch("iam_substrate.substrate_api.autoheal.run_autoheal", mock_autoheal):
            role_decay.check_and_heal()
        mock_autoheal.assert_called_once()
        flagged = mock_autoheal.call_args[0][0]
        assert any(f["id"] == "sick-01" for f in flagged)

    def test_check_and_heal_exception_does_not_propagate(self):
        """check_and_heal swallows exceptions from the DB layer."""
        from iam_substrate.substrate_api import role_decay

        mock_bad_session = MagicMock()
        mock_bad_session.query.side_effect = RuntimeError("DB unavailable")
        with patch("iam_substrate.substrate_api.database.get_session_local",
                   return_value=lambda: mock_bad_session):
            role_decay.check_and_heal()  # must not raise


class TestPruneTelemetry:
    """Tests for role_decay.prune_telemetry()."""

    def test_prune_with_zero_retention_is_noop(self):
        """prune_telemetry does nothing when _TELEMETRY_RETENTION_HOURS is 0."""
        from iam_substrate.substrate_api import role_decay

        orig = role_decay._TELEMETRY_RETENTION_HOURS
        try:
            role_decay._TELEMETRY_RETENTION_HOURS = 0
            mock_session = MagicMock()
            with patch("iam_substrate.substrate_api.database.get_session_local",
                       return_value=lambda: mock_session):
                role_decay.prune_telemetry()
            mock_session.query.assert_not_called()
        finally:
            role_decay._TELEMETRY_RETENTION_HOURS = orig

    def test_prune_deletes_old_records(self):
        """prune_telemetry deletes records older than retention window."""
        from iam_substrate.substrate_api import role_decay
        from iam_substrate.substrate_api.models import TelemetryRecord

        session, _ = _make_in_memory_session()

        # Insert an old record (naive datetime for SQLite)
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        record = TelemetryRecord(
            identity_id="old-01", S=0.8, delta_S=0.0, Q=1.0, tau=1.0,
            nabla_phi=0.0, field_state="stable",
            recorded_at=old_time.replace(tzinfo=None),
        )
        session.add(record)
        session.commit()
        assert session.query(TelemetryRecord).count() == 1

        orig = role_decay._TELEMETRY_RETENTION_HOURS
        try:
            role_decay._TELEMETRY_RETENTION_HOURS = 24
            with patch("iam_substrate.substrate_api.database.get_session_local",
                       return_value=lambda: session):
                role_decay.prune_telemetry()
            assert session.query(TelemetryRecord).count() == 0
        finally:
            role_decay._TELEMETRY_RETENTION_HOURS = orig

    def test_prune_handles_db_exception(self):
        """prune_telemetry catches and logs DB exceptions without raising."""
        from iam_substrate.substrate_api import role_decay

        orig = role_decay._TELEMETRY_RETENTION_HOURS
        try:
            role_decay._TELEMETRY_RETENTION_HOURS = 24
            mock_session = MagicMock()
            mock_session.query.side_effect = RuntimeError("DB exploded")
            with patch("iam_substrate.substrate_api.database.get_session_local",
                       return_value=lambda: mock_session):
                role_decay.prune_telemetry()  # must not raise
        finally:
            role_decay._TELEMETRY_RETENTION_HOURS = orig


class TestRunFloatLedgerAndParquet:
    """Tests for role_decay scheduler jobs that delegate to lambda handlers."""

    def test_run_float_ledger_delegates_to_handler(self):
        """run_float_ledger calls beacon_core.lambdas.generate_float_ledger.handler."""
        from iam_substrate.substrate_api import role_decay

        mock_handler = MagicMock(return_value={"csv_location": "s3://bucket/ledger.csv"})
        with patch("beacon_core.lambdas.generate_float_ledger.handler.handler", mock_handler):
            role_decay.run_float_ledger()
        mock_handler.assert_called_once()

    def test_run_float_ledger_catches_import_error(self):
        """run_float_ledger handles ImportError without raising."""
        from iam_substrate.substrate_api import role_decay

        with patch.dict(sys.modules, {"beacon_core.lambdas.generate_float_ledger.handler": None}):
            role_decay.run_float_ledger()  # must not raise

    def test_run_parquet_export_delegates_to_handler(self):
        """run_parquet_export calls beacon_core.lambdas.export_parquet.handler."""
        from iam_substrate.substrate_api import role_decay

        mock_handler = MagicMock(return_value={"record_count": 42, "parquet_location": "s3://b/out.parquet"})
        with patch("beacon_core.lambdas.export_parquet.handler.handler", mock_handler):
            role_decay.run_parquet_export()
        mock_handler.assert_called_once()

    def test_run_parquet_export_catches_exception(self):
        """run_parquet_export handles exceptions without raising."""
        from iam_substrate.substrate_api import role_decay

        with patch("beacon_core.lambdas.export_parquet.handler.handler",
                   side_effect=RuntimeError("S3 unavailable")):
            role_decay.run_parquet_export()  # must not raise


class TestStartStopScheduler:
    """Tests for role_decay.start_scheduler() and stop_scheduler()."""

    def test_start_scheduler_is_idempotent(self):
        """Calling start_scheduler twice only starts the scheduler once."""
        from iam_substrate.substrate_api import role_decay

        orig_started = role_decay._scheduler_started
        orig_scheduler = role_decay._scheduler

        mock_sched = MagicMock()
        try:
            role_decay._scheduler = mock_sched
            role_decay._scheduler_started = False
            role_decay.start_scheduler()
            role_decay.start_scheduler()  # second call — should be a no-op
            mock_sched.start.assert_called_once()
        finally:
            try:
                role_decay.stop_scheduler()
            except Exception:
                pass
            role_decay._scheduler = orig_scheduler
            role_decay._scheduler_started = orig_started

    def test_stop_scheduler_calls_shutdown(self):
        """stop_scheduler calls scheduler.shutdown when started."""
        from iam_substrate.substrate_api import role_decay

        orig_started = role_decay._scheduler_started
        orig_scheduler = role_decay._scheduler

        mock_sched = MagicMock()
        try:
            role_decay._scheduler = mock_sched
            role_decay._scheduler_started = True
            role_decay.stop_scheduler()
            mock_sched.shutdown.assert_called_once_with(wait=False)
            assert role_decay._scheduler_started is False
        finally:
            role_decay._scheduler = orig_scheduler
            role_decay._scheduler_started = orig_started

    def test_stop_scheduler_noop_when_not_started(self):
        """stop_scheduler does nothing when _scheduler_started is False."""
        from iam_substrate.substrate_api import role_decay

        orig_started = role_decay._scheduler_started
        orig_scheduler = role_decay._scheduler

        mock_sched = MagicMock()
        try:
            role_decay._scheduler = mock_sched
            role_decay._scheduler_started = False
            role_decay.stop_scheduler()
            mock_sched.shutdown.assert_not_called()
        finally:
            role_decay._scheduler = orig_scheduler
            role_decay._scheduler_started = orig_started


# ── iam_substrate/substrate_api/autoheal.py — GitHub PR skipped path ─────────


class TestOpenGithubPrSkipped:
    """Tests for _open_github_pr skipped-configuration path."""

    def test_open_github_pr_skipped_when_no_repo(self):
        """_open_github_pr returns 'skipped' message when GH_APP_REPO is empty."""
        from iam_substrate.substrate_api.autoheal import _open_github_pr
        import iam_substrate.substrate_api.autoheal as ah

        orig_id = ah.GH_APP_ID
        orig_repo = ah.GH_APP_REPO
        orig_inst = ah.GH_APP_INSTALLATION_ID
        try:
            ah.GH_APP_ID = "12345"
            ah.GH_APP_REPO = ""
            ah.GH_APP_INSTALLATION_ID = ""
            identity = {"id": "id-gh-01", "S": 0.5, "field_state": "incident"}
            result = _open_github_pr(identity)
            assert "skipped" in result
        finally:
            ah.GH_APP_ID = orig_id
            ah.GH_APP_REPO = orig_repo
            ah.GH_APP_INSTALLATION_ID = orig_inst

    def test_open_github_pr_handles_github_exception(self):
        """_open_github_pr returns 'failed: ...' when PyGithub raises."""
        from iam_substrate.substrate_api.autoheal import _open_github_pr
        import iam_substrate.substrate_api.autoheal as ah

        orig_id = ah.GH_APP_ID
        orig_repo = ah.GH_APP_REPO
        orig_inst = ah.GH_APP_INSTALLATION_ID
        orig_key = ah.GH_APP_PRIVATE_KEY
        try:
            ah.GH_APP_ID = "12345"
            ah.GH_APP_REPO = "org/repo"
            ah.GH_APP_INSTALLATION_ID = "67890"
            ah.GH_APP_PRIVATE_KEY = "FAKE_PEM"

            mock_gi = MagicMock()
            mock_gi.get_installation.side_effect = RuntimeError("GitHub API unreachable")
            mock_auth_cls = MagicMock(return_value=MagicMock())
            mock_gi_cls = MagicMock(return_value=mock_gi)

            with patch.dict(sys.modules, {
                "github": MagicMock(
                    GithubIntegration=mock_gi_cls,
                    Auth=MagicMock(AppAuth=mock_auth_cls),
                )
            }):
                identity = {"id": "id-gh-02", "S": 0.4, "field_state": "incident"}
                result = _open_github_pr(identity)
            assert "failed" in result
        finally:
            ah.GH_APP_ID = orig_id
            ah.GH_APP_REPO = orig_repo
            ah.GH_APP_INSTALLATION_ID = orig_inst
            ah.GH_APP_PRIVATE_KEY = orig_key
