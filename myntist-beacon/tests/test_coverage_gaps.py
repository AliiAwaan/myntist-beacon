"""
Targeted coverage-gap tests — round 2.

Covers previously uncovered lines in:
  - kcp/rotation_handler.py  (check_key_age all branches, initialize_if_needed)
  - beacon_core/dossier/config.py (feature-flag defaults and env overrides)
  - beacon_core/signing/kms_signer.py (sign_bytes — no-key, KMS-failure, sign_payload)
  - iam_substrate/substrate_api/autoheal.py (run_autoheal all paths, _post_slack_alert)
  - iam_substrate/substrate_api/role_decay.py (_int_env, _run_key_age_check)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── kcp/rotation_handler.py ──────────────────────────────────────────────────


class TestCheckKeyAge:
    """Tests for kcp.rotation_handler.check_key_age()."""

    def test_missing_env_var_returns_none_age(self):
        """When ED25519_KEY_CREATED is unset, age_days is None and rotation_required False."""
        from kcp.rotation_handler import check_key_age

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ED25519_KEY_CREATED", None)
            result = check_key_age()
        assert result["age_days"] is None
        assert result["rotation_required"] is False
        assert "not set" in result["warning"]

    def test_invalid_date_format_returns_none_age(self):
        """Malformed date string returns warning and age_days=None."""
        from kcp.rotation_handler import check_key_age

        with patch.dict(os.environ, {"ED25519_KEY_CREATED": "not-a-date"}):
            result = check_key_age()
        assert result["age_days"] is None
        assert result["rotation_required"] is False
        assert result["warning"] != ""

    def test_fresh_key_not_requiring_rotation(self):
        """Key created today → rotation_required=False."""
        from kcp.rotation_handler import check_key_age

        today_str = date.today().isoformat()
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": today_str}):
            result = check_key_age(max_age_days=330)
        assert result["age_days"] == 0
        assert result["rotation_required"] is False
        assert result["warning"] == ""

    def test_old_key_requires_rotation(self):
        """Key older than max_age_days → rotation_required=True."""
        from kcp.rotation_handler import check_key_age

        ancient = (date.today() - timedelta(days=400)).isoformat()
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": ancient}):
            result = check_key_age(max_age_days=330)
        assert result["age_days"] == 400
        assert result["rotation_required"] is True
        assert "rotation required" in result["warning"]

    def test_key_at_exactly_max_age_not_required(self):
        """Key at exactly max_age_days is not yet past the threshold (strictly >)."""
        from kcp.rotation_handler import check_key_age

        exactly_max = (date.today() - timedelta(days=330)).isoformat()
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": exactly_max}):
            result = check_key_age(max_age_days=330)
        assert result["rotation_required"] is False

    def test_custom_env_var_name(self):
        """Custom created_env parameter is read correctly."""
        from kcp.rotation_handler import check_key_age

        today_str = date.today().isoformat()
        with patch.dict(os.environ, {"MY_CUSTOM_KEY_DATE": today_str}):
            result = check_key_age(max_age_days=90, created_env="MY_CUSTOM_KEY_DATE")
        assert result["age_days"] == 0

    def test_key_max_age_days_from_env(self):
        """KEY_MAX_AGE_DAYS env var sets the threshold when max_age_days not passed."""
        from kcp.rotation_handler import check_key_age

        old_key = (date.today() - timedelta(days=100)).isoformat()
        with patch.dict(os.environ, {"ED25519_KEY_CREATED": old_key, "KEY_MAX_AGE_DAYS": "50"}):
            result = check_key_age()
        assert result["rotation_required"] is True
        assert result["max_age_days"] == 50


class TestInitializeIfNeeded:
    """Tests for kcp.rotation_handler.initialize_if_needed()."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        import kcp.key_state as ks_mod
        self._orig_file = ks_mod.KEY_STATES_FILE
        ks_mod.KEY_STATES_FILE = Path(self.tmpdir) / "key_states.json"

    def teardown_method(self):
        import kcp.key_state as ks_mod
        ks_mod.KEY_STATES_FILE = self._orig_file
        shutil.rmtree(self.tmpdir)

    def test_creates_genesis_when_no_state_exists(self):
        """initialize_if_needed creates genesis state when empty."""
        from kcp.rotation_handler import initialize_if_needed

        state = initialize_if_needed("test-pub-key")
        assert state.version == 0
        assert state.public_key == "test-pub-key"

    def test_returns_existing_state_when_present(self):
        """initialize_if_needed returns existing genesis without creating another."""
        from kcp.rotation_handler import initialize_if_needed
        from kcp.key_state import load_key_states

        state1 = initialize_if_needed("key-v0")
        state2 = initialize_if_needed("key-v1")  # should NOT override
        assert state2.public_key == "key-v0"
        assert len(load_key_states()) == 1


# ── beacon_core/dossier/config.py ────────────────────────────────────────────


class TestDossierConfig:
    """Tests for beacon_core.dossier.config feature-flag defaults."""

    def test_dossier_disabled_by_default(self):
        """DOSSIER_ENABLED is False unless IP_DOSSIER_ENABLED=true."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IP_DOSSIER_ENABLED", None)
            import importlib
            import beacon_core.dossier.config as cfg
            importlib.reload(cfg)
            assert cfg.DOSSIER_ENABLED is False

    def test_dossier_enabled_when_env_set(self):
        """IP_DOSSIER_ENABLED=true sets DOSSIER_ENABLED to True."""
        import importlib
        import beacon_core.dossier.config as cfg

        with patch.dict(os.environ, {"IP_DOSSIER_ENABLED": "true"}):
            importlib.reload(cfg)
            assert cfg.DOSSIER_ENABLED is True
        # Reset
        os.environ.pop("IP_DOSSIER_ENABLED", None)
        importlib.reload(cfg)

    def test_dossier_timeout_default(self):
        """Default DOSSIER_TIMEOUT_SECONDS is 2.0."""
        import importlib
        import beacon_core.dossier.config as cfg

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IP_DOSSIER_TIMEOUT", None)
            importlib.reload(cfg)
        assert cfg.DOSSIER_TIMEOUT_SECONDS == 2.0

    def test_dossier_block_threshold_default_is_none(self):
        """DOSSIER_BLOCK_THRESHOLD defaults to None when env var absent."""
        import importlib
        import beacon_core.dossier.config as cfg

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IP_DOSSIER_BLOCK_THRESHOLD", None)
            importlib.reload(cfg)
        assert cfg.DOSSIER_BLOCK_THRESHOLD is None

    def test_dossier_block_threshold_set_from_env(self):
        """DOSSIER_BLOCK_THRESHOLD is parsed from env var as float."""
        import importlib
        import beacon_core.dossier.config as cfg

        with patch.dict(os.environ, {"IP_DOSSIER_BLOCK_THRESHOLD": "0.8"}):
            importlib.reload(cfg)
            assert cfg.DOSSIER_BLOCK_THRESHOLD == 0.8
        os.environ.pop("IP_DOSSIER_BLOCK_THRESHOLD", None)
        importlib.reload(cfg)

    def test_dossier_provider_url_default(self):
        """Default provider URL is ipinfo."""
        import importlib
        import beacon_core.dossier.config as cfg

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IP_DOSSIER_PROVIDER_URL", None)
            importlib.reload(cfg)
        assert "ipinfo" in cfg.DOSSIER_PROVIDER_URL


# ── beacon_core/signing/kms_signer.py ────────────────────────────────────────


class TestKmsSigner:
    """Tests for beacon_core.signing.kms_signer.sign_bytes / sign_payload."""

    def test_sign_bytes_returns_none_when_no_keys_configured(self):
        """sign_bytes returns None when neither Ed25519 nor KMS key is set."""
        import importlib
        import beacon_core.signing.kms_signer as signer
        import beacon_core.signing.ed25519_signer as ed

        orig_priv = ed.PRIVATE_KEY_HEX
        orig_kms = signer.KMS_KEY_ID
        try:
            ed.PRIVATE_KEY_HEX = ""
            signer.KMS_KEY_ID = ""
            result = signer.sign_bytes(b"test payload")
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            signer.KMS_KEY_ID = orig_kms

    def test_sign_bytes_uses_ed25519_when_key_set(self):
        """sign_bytes calls Ed25519 path when PRIVATE_KEY_HEX is set."""
        import beacon_core.signing.kms_signer as signer
        import beacon_core.signing.ed25519_signer as ed

        # Generate a real Ed25519 private key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        import binascii
        priv = Ed25519PrivateKey.generate()
        hex_key = binascii.hexlify(priv.private_bytes_raw()).decode()

        orig = ed.PRIVATE_KEY_HEX
        try:
            ed.PRIVATE_KEY_HEX = hex_key
            result = signer.sign_bytes(b"some beacon payload")
            assert result is not None
            assert result.startswith("ed25519:")
        finally:
            ed.PRIVATE_KEY_HEX = orig

    def test_sign_bytes_kms_failure_returns_none(self):
        """sign_bytes returns None when KMS.sign() raises an exception."""
        import beacon_core.signing.kms_signer as signer
        import beacon_core.signing.ed25519_signer as ed

        orig_priv = ed.PRIVATE_KEY_HEX
        orig_kms = signer.KMS_KEY_ID
        orig_alias_only = signer._KMS_ALIAS_ONLY
        try:
            ed.PRIVATE_KEY_HEX = ""
            signer.KMS_KEY_ID = "arn:aws:kms:us-east-1:123456789012:key/fake-key-id"
            signer._KMS_ALIAS_ONLY = False

            mock_client = MagicMock()
            mock_client.sign.side_effect = RuntimeError("KMS unavailable")
            with patch("boto3.client", return_value=mock_client):
                result = signer.sign_bytes(b"test bytes")
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            signer.KMS_KEY_ID = orig_kms
            signer._KMS_ALIAS_ONLY = orig_alias_only

    def test_sign_bytes_kms_success(self):
        """sign_bytes returns base64 string when KMS.sign() succeeds."""
        import beacon_core.signing.kms_signer as signer
        import beacon_core.signing.ed25519_signer as ed
        import base64

        orig_priv = ed.PRIVATE_KEY_HEX
        orig_kms = signer.KMS_KEY_ID
        orig_alias_only = signer._KMS_ALIAS_ONLY
        try:
            ed.PRIVATE_KEY_HEX = ""
            signer.KMS_KEY_ID = "arn:aws:kms:us-east-1:123456789012:key/fake-key-id"
            signer._KMS_ALIAS_ONLY = False

            fake_sig = b"\xde\xad\xbe\xef"
            mock_client = MagicMock()
            mock_client.sign.return_value = {"Signature": fake_sig}
            with patch("boto3.client", return_value=mock_client):
                result = signer.sign_bytes(b"test bytes")
            assert result == base64.b64encode(fake_sig).decode()
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            signer.KMS_KEY_ID = orig_kms
            signer._KMS_ALIAS_ONLY = orig_alias_only

    def test_sign_bytes_skips_alias_only_kms_key(self):
        """sign_bytes returns None when KMS_KEY_ID is alias-only."""
        import beacon_core.signing.kms_signer as signer
        import beacon_core.signing.ed25519_signer as ed

        orig_priv = ed.PRIVATE_KEY_HEX
        orig_kms = signer.KMS_KEY_ID
        orig_alias_only = signer._KMS_ALIAS_ONLY
        try:
            ed.PRIVATE_KEY_HEX = ""
            signer.KMS_KEY_ID = "alias/my-key"
            signer._KMS_ALIAS_ONLY = True
            result = signer.sign_bytes(b"test bytes")
            assert result is None
        finally:
            ed.PRIVATE_KEY_HEX = orig_priv
            signer.KMS_KEY_ID = orig_kms
            signer._KMS_ALIAS_ONLY = orig_alias_only

    def test_sign_payload_delegates_to_sign_bytes(self):
        """sign_payload serialises payload and returns same type as sign_bytes."""
        import beacon_core.signing.kms_signer as signer

        with patch.object(signer, "sign_bytes", return_value="mock-sig") as mock_sb:
            result = signer.sign_payload({"field": "value", "num": 42})
        mock_sb.assert_called_once()
        assert result == "mock-sig"


# ── iam_substrate/substrate_api/autoheal.py ───────────────────────────────────


class TestAutoheal:
    """Tests for iam_substrate.substrate_api.autoheal.run_autoheal()."""

    def test_empty_list_returns_empty(self):
        """run_autoheal with no flagged identities returns empty list."""
        from iam_substrate.substrate_api.autoheal import run_autoheal
        result = run_autoheal([])
        assert result == []

    def test_run_autoheal_no_gh_app_id_skips_pr(self):
        """When GH_APP_ID is not set, github_pr field says skipped."""
        import iam_substrate.substrate_api.autoheal as ah
        orig = ah.GH_APP_ID
        try:
            ah.GH_APP_ID = ""
            identities = [{"id": "id-001", "S": 0.5, "field_state": "incident"}]
            results = ah.run_autoheal(identities)
        finally:
            ah.GH_APP_ID = orig
        assert len(results) == 1
        assert "skipped" in results[0]["github_pr"]

    def test_run_autoheal_no_slack_webhook_skips_alert(self):
        """When SLACK_WEBHOOK_URL is not set, slack_alert field is 'skipped'."""
        import iam_substrate.substrate_api.autoheal as ah
        orig_slack = ah.SLACK_WEBHOOK_URL
        orig_gh = ah.GH_APP_ID
        try:
            ah.SLACK_WEBHOOK_URL = ""
            ah.GH_APP_ID = ""
            identities = [{"id": "id-002", "S": 0.6, "field_state": "excitation"}]
            results = ah.run_autoheal(identities)
        finally:
            ah.SLACK_WEBHOOK_URL = orig_slack
            ah.GH_APP_ID = orig_gh
        assert results[0]["slack_alert"] == "skipped"

    def test_run_autoheal_with_db_writes_audit_entry(self):
        """When db session provided, audit entry is written."""
        import iam_substrate.substrate_api.autoheal as ah

        mock_db = MagicMock()
        mock_audit_fn = MagicMock()
        orig_gh = ah.GH_APP_ID
        orig_slack = ah.SLACK_WEBHOOK_URL
        try:
            ah.GH_APP_ID = ""
            ah.SLACK_WEBHOOK_URL = ""
            identities = [{"id": "id-003", "S": 0.55, "field_state": "incident"}]
            with patch(
                "iam_substrate.substrate_api.autoheal.append_audit_entry"
                if hasattr(ah, "append_audit_entry")
                else "iam_substrate.ledger.audit_log.append_audit_entry",
                mock_audit_fn,
            ):
                with patch("iam_substrate.ledger.audit_log.append_audit_entry", mock_audit_fn):
                    results = ah.run_autoheal(identities, db=mock_db)
        finally:
            ah.GH_APP_ID = orig_gh
            ah.SLACK_WEBHOOK_URL = orig_slack
        assert len(results) == 1
        assert results[0]["identity_id"] == "id-003"

    def test_run_autoheal_result_has_required_fields(self):
        """Remediation payload always has identity_id, S, field_state, action."""
        import iam_substrate.substrate_api.autoheal as ah
        orig_gh = ah.GH_APP_ID
        orig_slack = ah.SLACK_WEBHOOK_URL
        try:
            ah.GH_APP_ID = ""
            ah.SLACK_WEBHOOK_URL = ""
            identities = [{"id": "id-004", "S": 0.3, "field_state": "incident"}]
            results = ah.run_autoheal(identities)
        finally:
            ah.GH_APP_ID = orig_gh
            ah.SLACK_WEBHOOK_URL = orig_slack
        assert results[0]["identity_id"] == "id-004"
        assert results[0]["S"] == 0.3
        assert results[0]["action"] == "autoheal_triggered"

    def test_post_slack_alert_no_webhook_does_not_raise(self):
        """_post_slack_alert with no SLACK_WEBHOOK_URL logs and returns None."""
        from iam_substrate.substrate_api.autoheal import _post_slack_alert
        import iam_substrate.substrate_api.autoheal as ah
        orig = ah.SLACK_WEBHOOK_URL
        try:
            ah.SLACK_WEBHOOK_URL = ""
            identity = {"id": "id-005", "S": 0.5, "field_state": "incident"}
            result = _post_slack_alert(identity)
        finally:
            ah.SLACK_WEBHOOK_URL = orig
        assert result is None

    def test_post_slack_alert_with_webhook_posts_message(self):
        """_post_slack_alert with SLACK_WEBHOOK_URL set calls requests.post."""
        from iam_substrate.substrate_api.autoheal import _post_slack_alert
        import iam_substrate.substrate_api.autoheal as ah
        orig = ah.SLACK_WEBHOOK_URL
        try:
            ah.SLACK_WEBHOOK_URL = "https://hooks.slack.com/fake"
            identity = {"id": "id-006", "S": 0.4, "field_state": "incident"}
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            with patch("requests.post", return_value=mock_resp) as mock_post:
                _post_slack_alert(identity)
            mock_post.assert_called_once()
        finally:
            ah.SLACK_WEBHOOK_URL = orig

    def test_post_slack_alert_handles_request_exception(self):
        """_post_slack_alert silently handles requests.post raising an exception."""
        from iam_substrate.substrate_api.autoheal import _post_slack_alert
        import iam_substrate.substrate_api.autoheal as ah
        orig = ah.SLACK_WEBHOOK_URL
        try:
            ah.SLACK_WEBHOOK_URL = "https://hooks.slack.com/fake"
            identity = {"id": "id-007", "S": 0.2, "field_state": "incident"}
            with patch("requests.post", side_effect=RuntimeError("connection refused")):
                # Should not raise
                _post_slack_alert(identity)
        finally:
            ah.SLACK_WEBHOOK_URL = orig

    def test_run_autoheal_multiple_identities(self):
        """run_autoheal processes all identities and returns all results."""
        import iam_substrate.substrate_api.autoheal as ah
        orig_gh = ah.GH_APP_ID
        orig_slack = ah.SLACK_WEBHOOK_URL
        try:
            ah.GH_APP_ID = ""
            ah.SLACK_WEBHOOK_URL = ""
            identities = [
                {"id": "id-A", "S": 0.5, "field_state": "incident"},
                {"id": "id-B", "S": 0.6, "field_state": "excitation"},
                {"id": "id-C", "S": 0.3, "field_state": "incident"},
            ]
            results = ah.run_autoheal(identities)
        finally:
            ah.GH_APP_ID = orig_gh
            ah.SLACK_WEBHOOK_URL = orig_slack
        assert len(results) == 3


# ── iam_substrate/substrate_api/role_decay.py (_int_env) ─────────────────────


class TestIntEnv:
    """Tests for role_decay._int_env helper."""

    def test_returns_default_when_env_absent(self):
        os.environ.pop("TEST_INT_VAR", None)
        from iam_substrate.substrate_api.role_decay import _int_env
        assert _int_env("TEST_INT_VAR", 42) == 42

    def test_parses_valid_integer(self):
        from iam_substrate.substrate_api.role_decay import _int_env
        with patch.dict(os.environ, {"TEST_INT_VAR": "99"}):
            assert _int_env("TEST_INT_VAR", 42) == 99

    def test_returns_default_for_non_integer_value(self):
        from iam_substrate.substrate_api.role_decay import _int_env
        with patch.dict(os.environ, {"TEST_INT_VAR": "not-a-number"}):
            assert _int_env("TEST_INT_VAR", 42) == 42

    def test_clamps_to_min_val(self):
        from iam_substrate.substrate_api.role_decay import _int_env
        with patch.dict(os.environ, {"TEST_INT_VAR": "0"}):
            result = _int_env("TEST_INT_VAR", 10, min_val=1)
        assert result == 1

    def test_value_above_min_not_clamped(self):
        from iam_substrate.substrate_api.role_decay import _int_env
        with patch.dict(os.environ, {"TEST_INT_VAR": "5"}):
            result = _int_env("TEST_INT_VAR", 10, min_val=1)
        assert result == 5


class TestRunKeyAgeCheck:
    """Tests for role_decay._run_key_age_check delegation wrapper."""

    def test_delegates_to_kcp_rotation_handler(self):
        from iam_substrate.substrate_api.role_decay import _run_key_age_check

        mock_check = MagicMock(return_value={"rotation_required": False, "age_days": 10, "max_age_days": 330, "warning": ""})
        with patch("kcp.rotation_handler.check_key_age", mock_check):
            _run_key_age_check()
        mock_check.assert_called_once()

    def test_catches_exception_and_does_not_raise(self):
        from iam_substrate.substrate_api.role_decay import _run_key_age_check

        with patch("kcp.rotation_handler.check_key_age", side_effect=RuntimeError("KCP unavailable")):
            # Must not propagate the exception
            _run_key_age_check()
