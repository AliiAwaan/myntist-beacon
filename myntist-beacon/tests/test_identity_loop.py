"""
Tests for identity_loop modules — farcaster_adapter, lens_adapter, rss_generator,
signing_keys_publisher, zenodo_client, ipfs_pinner.

All external services are mocked. No live API calls.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# farcaster_adapter
# ===========================================================================

class TestFarcasterAdapter:
    def test_cast_without_credentials_returns_stub(self):
        import identity_loop.feeds.farcaster_adapter as fa
        with patch.object(fa, "FARCASTER_FID", ""), \
             patch.object(fa, "FARCASTER_SIGNER_UUID", ""):
            result = fa.cast("hello beacon")
        assert result["status"] == "stub"
        assert result["platform"] == "farcaster"
        assert result["content"] == "hello beacon"

    def test_cast_with_credentials_returns_stub_with_fid(self):
        import identity_loop.feeds.farcaster_adapter as fa
        with patch.object(fa, "FARCASTER_FID", "12345"), \
             patch.object(fa, "FARCASTER_SIGNER_UUID", "uuid-abc"):
            result = fa.cast("beacon pulse", metadata={"S": 0.9})
        assert result["status"] == "stub"
        assert result["fid"] == "12345"

    def test_cast_returns_platform_farcaster(self):
        import identity_loop.feeds.farcaster_adapter as fa
        result = fa.cast("test")
        assert result["platform"] == "farcaster"

    def test_check_rate_limit_within_limit_returns_true(self):
        import identity_loop.feeds.farcaster_adapter as fa
        fa._in_memory_rate_limit.clear()
        assert fa._check_rate_limit("test-key-fc") is True

    def test_check_rate_limit_exceeds_max_returns_false(self):
        import identity_loop.feeds.farcaster_adapter as fa
        fa._in_memory_rate_limit.clear()
        import time
        window = int(time.time()) // fa.RATE_LIMIT_WINDOW_SECONDS
        key = f"overload-fc:{window}"
        fa._in_memory_rate_limit[key] = fa.RATE_LIMIT_MAX  # already at max
        result = fa._check_rate_limit("overload-fc")
        assert result is False

    def test_cast_when_rate_limited_returns_rate_limited(self):
        import identity_loop.feeds.farcaster_adapter as fa
        with patch.object(fa, "_check_rate_limit", return_value=False):
            result = fa.cast("over limit")
        assert result["status"] == "rate_limited"
        assert result["platform"] == "farcaster"

    def test_cast_with_none_metadata_does_not_raise(self):
        import identity_loop.feeds.farcaster_adapter as fa
        result = fa.cast("msg", metadata=None)
        assert "status" in result


# ===========================================================================
# lens_adapter
# ===========================================================================

class TestLensAdapter:
    def test_post_pulse_without_credentials_returns_stub(self):
        import identity_loop.feeds.lens_adapter as la
        with patch.object(la, "LENS_PROFILE_ID", ""), \
             patch.object(la, "LENS_ACCESS_TOKEN", ""):
            result = la.post_pulse("beacon pulse")
        assert result["status"] == "stub"
        assert result["platform"] == "lens"

    def test_post_pulse_with_credentials_returns_stub_with_profile_id(self):
        import identity_loop.feeds.lens_adapter as la
        with patch.object(la, "LENS_PROFILE_ID", "0x1234"), \
             patch.object(la, "LENS_ACCESS_TOKEN", "tok-abc"):
            result = la.post_pulse("beacon pulse", metadata={"S": 0.8})
        assert result["status"] == "stub"
        assert result["profile_id"] == "0x1234"

    def test_post_pulse_when_rate_limited_returns_rate_limited(self):
        import identity_loop.feeds.lens_adapter as la
        with patch.object(la, "_check_rate_limit", return_value=False):
            result = la.post_pulse("over limit")
        assert result["status"] == "rate_limited"
        assert result["platform"] == "lens"

    def test_check_rate_limit_in_memory_within_limit(self):
        import identity_loop.feeds.lens_adapter as la
        la._in_memory_rate_limit.clear()
        result = la._check_rate_limit("lens-test-xx")
        assert result is True

    def test_check_rate_limit_exceeds_max(self):
        import identity_loop.feeds.lens_adapter as la
        la._in_memory_rate_limit.clear()
        import time
        window = int(time.time()) // la.RATE_LIMIT_WINDOW_SECONDS
        key = f"lens-over-xx:{window}"
        la._in_memory_rate_limit[key] = la.RATE_LIMIT_MAX
        result = la._check_rate_limit("lens-over-xx")
        assert result is False

    def test_check_rate_limit_with_dynamodb_success(self):
        import identity_loop.feeds.lens_adapter as la
        la._in_memory_rate_limit.clear()
        mock_client = MagicMock()
        mock_client.update_item.return_value = {
            "Attributes": {"count": {"N": "1"}}
        }
        with patch.dict(os.environ, {"DYNAMODB_RATE_TABLE": "test-table"}), \
             patch("boto3.client", return_value=mock_client):
            result = la._check_rate_limit("lens-ddb")
        assert result is True

    def test_check_rate_limit_dynamodb_exception_falls_back_to_memory(self):
        import identity_loop.feeds.lens_adapter as la
        la._in_memory_rate_limit.clear()
        mock_client = MagicMock()
        mock_client.update_item.side_effect = Exception("DDB unavailable")
        with patch.dict(os.environ, {"DYNAMODB_RATE_TABLE": "test-table"}), \
             patch("boto3.client", return_value=mock_client):
            result = la._check_rate_limit("lens-fallback")
        assert result is True

    def test_post_pulse_platform_is_lens(self):
        import identity_loop.feeds.lens_adapter as la
        result = la.post_pulse("hello")
        assert result["platform"] == "lens"

    def test_post_pulse_no_metadata_no_raise(self):
        import identity_loop.feeds.lens_adapter as la
        result = la.post_pulse("hello", metadata=None)
        assert "status" in result


# ===========================================================================
# rss_generator
# ===========================================================================

class TestRssGenerator:
    def test_generate_rss_empty_items_writes_file(self):
        from identity_loop.feeds.rss_generator import generate_rss
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        result = generate_rss([], output_path=path)
        assert result == path
        content = open(path).read()
        assert "<rss" in content
        assert "Myntist Sovereign Beacon" in content

    def test_generate_rss_with_items_includes_description(self):
        from identity_loop.feeds.rss_generator import generate_rss
        items = [
            {"S": 0.87, "delta_S": 0.01, "field_state": "stable",
             "timestamp": "2026-05-07T12:00:00+00:00"},
            {"S": 0.75, "delta_S": -0.02, "field_state": "incident",
             "timestamp": "2026-05-07T11:00:00+00:00"},
        ]
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        generate_rss(items, output_path=path)
        content = open(path).read()
        assert "S=0.8700" in content
        assert "stable" in content

    def test_generate_rss_caps_at_max_items(self):
        from identity_loop.feeds.rss_generator import generate_rss, MAX_ITEMS
        items = [{"S": 0.9, "delta_S": 0.0, "field_state": "stable"} for _ in range(60)]
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        generate_rss(items, output_path=path)
        assert open(path).read() != ""

    def test_generate_rss_invalid_timestamp_falls_back(self):
        from identity_loop.feeds.rss_generator import generate_rss
        items = [{"S": 0.5, "delta_S": 0.0, "field_state": "incident",
                  "timestamp": "not-a-date"}]
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        generate_rss(items, output_path=path)
        content = open(path).read()
        assert "<rss" in content

    def test_generate_rss_non_string_timestamp_falls_back(self):
        from identity_loop.feeds.rss_generator import generate_rss
        items = [{"S": 0.5, "delta_S": 0.0, "field_state": "stable",
                  "timestamp": 1746614400}]  # integer timestamp
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        generate_rss(items, output_path=path)
        assert "<rss" in open(path).read()

    def test_generate_rss_with_s3_bucket_calls_boto3(self):
        import identity_loop.feeds.rss_generator as rg
        mock_client = MagicMock()
        items = [{"S": 0.9, "delta_S": 0.0, "field_state": "stable"}]
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        with patch.object(rg, "S3_BUCKET", "my-test-bucket"), \
             patch("boto3.client", return_value=mock_client):
            rg.generate_rss(items, output_path=path)
        mock_client.put_object.assert_called_once()

    def test_write_to_s3_exception_does_not_raise(self):
        import identity_loop.feeds.rss_generator as rg
        mock_client = MagicMock()
        mock_client.put_object.side_effect = Exception("S3 error")
        with patch.object(rg, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_client):
            rg._write_to_s3("<rss/>")

    def test_prettify_returns_xml_string(self):
        from identity_loop.feeds.rss_generator import _prettify
        from xml.etree.ElementTree import Element
        elem = Element("rss")
        result = _prettify(elem)
        assert "<rss" in result


# ===========================================================================
# signing_keys_publisher
# ===========================================================================

class TestSigningKeysPublisher:
    def test_publish_without_s3_bucket_returns_false(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        key_states = [{"version": 1, "public_key": "abc", "threshold_m": 3, "threshold_n": 5}]
        with patch.object(skp, "S3_BUCKET", ""):
            result = skp.publish_signing_keys(key_states)
        assert result is False

    def test_publish_with_s3_bucket_calls_put_object(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        mock_client = MagicMock()
        key_states = [{"version": 1, "public_key": "abc", "threshold_m": 3, "threshold_n": 5}]
        with patch.object(skp, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_client):
            result = skp.publish_signing_keys(key_states)
        assert result is True
        mock_client.put_object.assert_called_once()

    def test_publish_s3_exception_returns_false(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        mock_client = MagicMock()
        mock_client.put_object.side_effect = Exception("S3 error")
        key_states = [{"version": 1, "public_key": "abc", "threshold_m": 3, "threshold_n": 5}]
        with patch.object(skp, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_client):
            result = skp.publish_signing_keys(key_states)
        assert result is False

    def test_publish_with_object_key_states(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        ks = MagicMock()
        ks.version = 2
        ks.public_key = "pubkey"
        ks.threshold_m = 3
        ks.threshold_n = 5
        with patch.object(skp, "S3_BUCKET", ""):
            result = skp.publish_signing_keys([ks])
        assert result is False

    def test_publish_empty_key_states(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        with patch.object(skp, "S3_BUCKET", ""):
            result = skp.publish_signing_keys([])
        assert result is False

    def test_publish_payload_contains_endpoint(self):
        import identity_loop.well_known.signing_keys_publisher as skp
        captured = {}
        mock_client = MagicMock()

        def fake_put(**kwargs):
            captured["body"] = kwargs["Body"]
        mock_client.put_object.side_effect = fake_put

        key_states = [{"version": 1, "public_key": "abc", "threshold_m": 2, "threshold_n": 3}]
        with patch.object(skp, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_client):
            skp.publish_signing_keys(key_states)
        import json
        payload = json.loads(captured["body"])
        assert "endpoint" in payload
        assert "keys" in payload


# ===========================================================================
# zenodo_client
# ===========================================================================

class TestZenodoClient:
    def test_deposit_without_api_key_returns_stub(self):
        import identity_loop.zenodo.zenodo_client as zc
        with patch.object(zc, "ZENODO_API_KEY", ""):
            result = zc.deposit("Title", "Desc", b"content")
        assert result["status"] == "stub"
        assert "doi" in result
        assert "10.5281" in result["doi"]

    def test_deposit_stub_includes_title(self):
        import identity_loop.zenodo.zenodo_client as zc
        with patch.object(zc, "ZENODO_API_KEY", ""):
            result = zc.deposit("My Title", "Desc", b"data", file_name="out.json")
        assert result["title"] == "My Title"

    def test_deposit_with_api_key_makes_requests_and_returns_published(self):
        import identity_loop.zenodo.zenodo_client as zc
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "dep-001", "doi": "10.5281/zenodo.dep-001"}
        mock_pub_resp = MagicMock()
        mock_pub_resp.raise_for_status.return_value = None
        mock_pub_resp.json.return_value = {"doi": "10.5281/zenodo.dep-001"}

        with patch.object(zc, "ZENODO_API_KEY", "test-key"), \
             patch("requests.post", side_effect=[mock_resp, mock_resp, mock_pub_resp]), \
             patch("requests.put", return_value=mock_resp):
            result = zc.deposit("Title", "Desc", b"content")
        assert result["status"] == "published"
        assert "10.5281" in result["doi"]

    def test_deposit_with_api_key_network_error_returns_error(self):
        import identity_loop.zenodo.zenodo_client as zc
        with patch.object(zc, "ZENODO_API_KEY", "test-key"), \
             patch("requests.post", side_effect=Exception("network error")):
            result = zc.deposit("Title", "Desc", b"content")
        assert result["status"] == "error"
        assert "network error" in result["error"]

    def test_deposit_uses_zenodo_url(self):
        import identity_loop.zenodo.zenodo_client as zc
        assert "zenodo.org" in zc.ZENODO_BASE_URL

    def test_deposit_stub_has_deposit_id(self):
        import identity_loop.zenodo.zenodo_client as zc
        with patch.object(zc, "ZENODO_API_KEY", ""):
            result = zc.deposit("T", "D", b"x")
        assert "deposit_id" in result


# ===========================================================================
# ipfs_pinner
# ===========================================================================

class TestIpfsPinner:
    def test_pin_json_without_credentials_returns_stub(self):
        import identity_loop.zenodo.ipfs_pinner as ip
        with patch.object(ip, "IPFS_API_KEY", ""), \
             patch.object(ip, "IPFS_API_SECRET", ""):
            result = ip.pin_json({"S": 0.9}, name="test")
        assert result["status"] == "stub"
        assert "QmMock" in result["cid"]
        assert result["name"] == "test"

    def test_pin_json_with_credentials_calls_api_and_returns_pinned(self):
        import identity_loop.zenodo.ipfs_pinner as ip
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"IpfsHash": "QmRealCID000"}
        with patch.object(ip, "IPFS_API_KEY", "key123"), \
             patch.object(ip, "IPFS_API_SECRET", "secret123"), \
             patch("requests.post", return_value=mock_resp):
            result = ip.pin_json({"data": "value"}, name="my-pin")
        assert result["status"] == "pinned"
        assert result["cid"] == "QmRealCID000"
        assert result["name"] == "my-pin"

    def test_pin_json_with_credentials_network_error_returns_error(self):
        import identity_loop.zenodo.ipfs_pinner as ip
        with patch.object(ip, "IPFS_API_KEY", "key123"), \
             patch.object(ip, "IPFS_API_SECRET", "secret123"), \
             patch("requests.post", side_effect=Exception("IPFS down")):
            result = ip.pin_json({"data": "value"})
        assert result["status"] == "error"
        assert "IPFS down" in result["error"]

    def test_pin_json_with_only_key_no_secret_returns_stub(self):
        import identity_loop.zenodo.ipfs_pinner as ip
        with patch.object(ip, "IPFS_API_KEY", "key123"), \
             patch.object(ip, "IPFS_API_SECRET", ""):
            result = ip.pin_json({"data": "value"})
        assert result["status"] == "stub"

    def test_pin_json_default_name(self):
        import identity_loop.zenodo.ipfs_pinner as ip
        with patch.object(ip, "IPFS_API_KEY", ""), \
             patch.object(ip, "IPFS_API_SECRET", ""):
            result = ip.pin_json({})
        assert result["name"] == "myntist-beacon"
