"""
Tests for beacon_core lambda handlers — export_parquet, generate_float_ledger,
generate_status.

All S3/boto3/DB/psycopg2 calls are mocked. No live AWS or PostgreSQL connections.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_psycopg2_mock():
    """Return a minimal psycopg2 stub so modules that import it don't crash."""
    mod = ModuleType("psycopg2")
    mod.connect = MagicMock()
    sys.modules.setdefault("psycopg2", mod)
    return mod


# ===========================================================================
# export_parquet/handler.py
# ===========================================================================

class TestExportParquetHandler:
    def test_handler_disabled_returns_skipped(self):
        import beacon_core.lambdas.export_parquet.handler as h
        with patch.object(h, "PARQUET_EXPORT_ENABLED", False):
            result = h.handler({}, None)
        assert result["status"] == "skipped"

    def test_handler_enabled_no_db_returns_result(self):
        import beacon_core.lambdas.export_parquet.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        fake_bytes = b"PARQUET_BYTES"
        with patch.object(h, "PARQUET_EXPORT_ENABLED", True), \
             patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.export_parquet.handler.TelemetryExporter",
                   return_value=mock_exporter), \
             patch.object(h, "_records_to_parquet", return_value=fake_bytes):
            result = h.handler({}, None)
        assert "record_count" in result
        assert result["record_count"] == 0
        assert "week" in result

    def test_handler_enabled_with_records(self):
        import beacon_core.lambdas.export_parquet.handler as h
        records = [
            {"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95, "nabla_phi": 0.0,
             "field_state": "stable", "float_yield": 0.055, "time": "2026-05-01",
             "identity_id": "id-01", "schema_version": "2.0"}
        ]
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = records
        with patch.object(h, "PARQUET_EXPORT_ENABLED", True), \
             patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.export_parquet.handler.TelemetryExporter",
                   return_value=mock_exporter):
            result = h.handler({}, None)
        assert result["record_count"] == 1

    def test_handler_with_s3_bucket_calls_boto3(self):
        import beacon_core.lambdas.export_parquet.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        fake_bytes = b"PARQUET_BYTES"
        with patch.object(h, "PARQUET_EXPORT_ENABLED", True), \
             patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("beacon_core.lambdas.export_parquet.handler.TelemetryExporter",
                   return_value=mock_exporter), \
             patch.object(h, "_records_to_parquet", return_value=fake_bytes), \
             patch("boto3.client", return_value=mock_s3):
            result = h.handler({}, None)
        mock_s3.put_object.assert_called_once()
        assert result["parquet_location"].startswith("s3://")

    def test_write_to_s3_or_tmp_no_bucket_writes_to_tmp(self):
        import beacon_core.lambdas.export_parquet.handler as h
        with patch.object(h, "S3_BUCKET", ""):
            path = h._write_to_s3_or_tmp("test/key.parquet", b"data", "application/octet-stream")
        assert "/tmp/" in path
        assert os.path.exists(path)

    def test_write_to_s3_or_tmp_s3_success(self):
        import beacon_core.lambdas.export_parquet.handler as h
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            path = h._write_to_s3_or_tmp("test/key.parquet", b"data", "application/octet-stream")
        assert path.startswith("s3://")

    def test_write_to_s3_or_tmp_s3_failure_falls_back_to_tmp(self):
        import beacon_core.lambdas.export_parquet.handler as h
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 down")
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            path = h._write_to_s3_or_tmp("test/key.parquet", b"data", "application/octet-stream")
        assert "/tmp/" in path

    def test_records_to_parquet_with_records_returns_bytes(self):
        import beacon_core.lambdas.export_parquet.handler as h
        records = [
            {"S": 0.9, "delta_S": 0.01, "Q": 1.0, "tau": 0.95, "nabla_phi": 0.0,
             "field_state": "stable", "float_yield": 0.05, "time": "2026-05-01",
             "identity_id": "id-01", "schema_version": "2.0",
             "liquidity_signal": 0.8, "coherence_signal": 0.9,
             "r_HSCE": 0.04, "float_reinvestment_rate": 0.06},
        ]
        result = h._records_to_parquet(records)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_records_to_parquet_none_fields_handled(self):
        import beacon_core.lambdas.export_parquet.handler as h
        records = [
            {"S": 0.9, "delta_S": None, "Q": None, "tau": None, "nabla_phi": None,
             "field_state": "stable", "float_yield": None, "time": None,
             "identity_id": None, "schema_version": None,
             "liquidity_signal": None, "coherence_signal": None,
             "r_HSCE": None, "float_reinvestment_rate": None},
        ]
        result = h._records_to_parquet(records)
        assert isinstance(result, bytes)

    def test_records_to_parquet_no_pyarrow_returns_json_bytes(self):
        import beacon_core.lambdas.export_parquet.handler as h
        records = [{"S": 0.9, "field_state": "stable"}]
        # Temporarily remove pyarrow from sys.modules to trigger ImportError path
        pa_backup = sys.modules.pop("pyarrow", None)
        pq_backup = sys.modules.pop("pyarrow.parquet", None)
        sys.modules["pyarrow"] = None  # type: ignore
        try:
            result = h._records_to_parquet(records)
        finally:
            if pa_backup is not None:
                sys.modules["pyarrow"] = pa_backup
            elif "pyarrow" in sys.modules:
                del sys.modules["pyarrow"]
            if pq_backup is not None:
                sys.modules["pyarrow.parquet"] = pq_backup
        assert isinstance(result, bytes)

    def test_handler_result_has_schema_version(self):
        import beacon_core.lambdas.export_parquet.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        with patch.object(h, "PARQUET_EXPORT_ENABLED", True), \
             patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.export_parquet.handler.TelemetryExporter",
                   return_value=mock_exporter), \
             patch.object(h, "_records_to_parquet", return_value=b"data"):
            result = h.handler({}, None)
        assert result["schema_version"] == "2.0"
        assert result["period_days"] == 7


# ===========================================================================
# generate_float_ledger/handler.py
# ===========================================================================

class TestGenerateFloatLedgerHandler:
    def test_handler_empty_records_returns_summary(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        with patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.generate_float_ledger.handler.TelemetryExporter",
                   return_value=mock_exporter):
            result = h.handler({}, None)
        assert "aggregates" in result
        assert result["aggregates"]["count"] == 0
        assert result["aggregates"]["avg_S"] is None

    def test_handler_with_records_computes_aggregates(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        records = [
            {"S": 0.9, "float_yield": 0.05, "liquidity_signal": 0.8,
             "r_HSCE": 0.04, "float_reinvestment_rate": 0.06,
             "delta_S": 0.01, "Q": 1.0, "tau": 0.9},
            {"S": 0.8, "float_yield": 0.04, "liquidity_signal": 0.7,
             "r_HSCE": 0.03, "float_reinvestment_rate": 0.05,
             "delta_S": -0.01, "Q": 1.0, "tau": 0.8},
        ]
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = records
        with patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.generate_float_ledger.handler.TelemetryExporter",
                   return_value=mock_exporter):
            result = h.handler({}, None)
        agg = result["aggregates"]
        assert agg["count"] == 2
        assert abs(agg["avg_S"] - 0.85) < 0.001
        assert abs(agg["total_float_yield"] - 0.09) < 0.001

    def test_handler_with_s3_calls_boto3_twice(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("beacon_core.lambdas.generate_float_ledger.handler.TelemetryExporter",
                   return_value=mock_exporter), \
             patch("boto3.client", return_value=mock_s3):
            result = h.handler({}, None)
        assert mock_s3.put_object.call_count >= 2
        assert result["csv_location"].startswith("s3://")
        assert result["json_location"].startswith("s3://")

    def test_handler_s3_failure_falls_back_to_tmp(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 down")
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("beacon_core.lambdas.generate_float_ledger.handler.TelemetryExporter",
                   return_value=mock_exporter), \
             patch("boto3.client", return_value=mock_s3):
            result = h.handler({}, None)
        assert "/tmp/" in result["csv_location"]

    def test_compute_aggregates_empty_returns_none_values(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _compute_aggregates
        agg = _compute_aggregates([])
        assert agg["count"] == 0
        assert agg["avg_S"] is None
        assert agg["avg_float_yield"] is None
        assert agg["total_float_yield"] is None
        assert agg["avg_liquidity_signal"] is None
        assert agg["avg_r_HSCE"] is None
        assert agg["avg_float_reinvestment_rate"] is None

    def test_compute_aggregates_partial_nulls(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _compute_aggregates
        records = [{"S": 0.9}, {"S": None, "float_yield": 0.05}]
        agg = _compute_aggregates(records)
        assert agg["count"] == 2
        assert agg["avg_S"] == 0.9
        assert agg["avg_float_yield"] == 0.05

    def test_compute_aggregates_all_fields_populated(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _compute_aggregates
        records = [
            {"S": 0.9, "float_yield": 0.05, "liquidity_signal": 0.8,
             "r_HSCE": 0.04, "float_reinvestment_rate": 0.06},
            {"S": 0.7, "float_yield": 0.03, "liquidity_signal": 0.6,
             "r_HSCE": 0.02, "float_reinvestment_rate": 0.04},
        ]
        agg = _compute_aggregates(records)
        assert abs(agg["avg_S"] - 0.8) < 0.001
        assert abs(agg["total_float_yield"] - 0.08) < 0.001
        assert abs(agg["avg_liquidity_signal"] - 0.7) < 0.001

    def test_build_csv_empty_returns_no_records_bytes(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _build_csv
        result = _build_csv([])
        assert b"no records" in result

    def test_build_csv_with_records_contains_header_and_row(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _build_csv
        records = [{"S": 0.9, "Q": 1.0, "tau": 0.9, "delta_S": 0.01,
                    "float_yield": 0.05, "identity_id": "id-01"}]
        result = _build_csv(records)
        assert b"S" in result
        assert b"float_yield" in result
        assert b"0.9" in result

    def test_build_csv_with_datetime_time_field(self):
        from beacon_core.lambdas.generate_float_ledger.handler import _build_csv
        from datetime import datetime, timezone
        records = [{"S": 0.9, "time": datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)}]
        result = _build_csv(records)
        assert b"2026-05-07" in result

    def test_write_to_s3_or_tmp_no_bucket_writes_tmp(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        with patch.object(h, "S3_BUCKET", ""):
            path = h._write_to_s3_or_tmp("float/key.csv", b"data", "text/csv")
        assert "/tmp/" in path

    def test_write_to_s3_or_tmp_s3_success(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            path = h._write_to_s3_or_tmp("float/key.csv", b"data", "text/csv")
        assert path.startswith("s3://")

    def test_handler_summary_has_schema_version(self):
        import beacon_core.lambdas.generate_float_ledger.handler as h
        mock_exporter = MagicMock()
        mock_exporter.get_recent_field_telemetry.return_value = []
        with patch.object(h, "S3_BUCKET", ""), \
             patch("beacon_core.lambdas.generate_float_ledger.handler.TelemetryExporter",
                   return_value=mock_exporter):
            result = h.handler({}, None)
        assert result["schema_version"] == "2.0"
        assert result["period_days"] == 30


# ===========================================================================
# generate_status/handler.py
# ===========================================================================

class TestGenerateStatusHandler:
    def test_fetch_live_telemetry_no_database_url_returns_none(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""):
            result = h._fetch_live_telemetry()
        assert result is None

    def test_fetch_live_telemetry_db_connection_error_returns_none(self):
        import beacon_core.lambdas.generate_status.handler as h
        psycopg2_mock = _make_psycopg2_mock()
        psycopg2_mock.connect.side_effect = Exception("Connection refused")
        with patch.object(h, "DATABASE_URL", "postgresql://fake:fake@fake/fake"), \
             patch.dict(sys.modules, {"psycopg2": psycopg2_mock}):
            result = h._fetch_live_telemetry()
        assert result is None

    def test_fetch_live_telemetry_empty_result_returns_none(self):
        import beacon_core.lambdas.generate_status.handler as h
        psycopg2_mock = _make_psycopg2_mock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cur
        psycopg2_mock.connect.return_value = mock_conn
        with patch.object(h, "DATABASE_URL", "postgresql://fake/fake"), \
             patch.dict(sys.modules, {"psycopg2": psycopg2_mock}):
            result = h._fetch_live_telemetry()
        assert result is None

    def test_fetch_live_telemetry_with_row_returns_dict(self):
        import beacon_core.lambdas.generate_status.handler as h
        psycopg2_mock = _make_psycopg2_mock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (0.87, 0.01, 1.0, 0.95, 0.02, "stable")
        mock_conn.cursor.return_value = mock_cur
        psycopg2_mock.connect.return_value = mock_conn
        with patch.object(h, "DATABASE_URL", "postgresql://fake/fake"), \
             patch.dict(sys.modules, {"psycopg2": psycopg2_mock}):
            result = h._fetch_live_telemetry()
        assert result is not None
        assert result["S"] == 0.87
        assert result["field_state"] == "stable"

    def test_write_to_s3_no_bucket_writes_to_tmp(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "field_state": "stable"}
        with patch.object(h, "S3_BUCKET", ""):
            result = h._write_to_s3("api/field/v1/status.json", payload)
        assert result is False

    def test_write_to_s3_with_bucket_calls_boto3(self):
        import beacon_core.lambdas.generate_status.handler as h
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            result = h._write_to_s3("api/field/v1/status.json", {"S": 0.9})
        assert result is True
        mock_s3.put_object.assert_called_once()

    def test_write_to_s3_exception_returns_false(self):
        import beacon_core.lambdas.generate_status.handler as h
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 down")
        with patch.object(h, "S3_BUCKET", "my-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            result = h._write_to_s3("api/field/v1/status.json", {"S": 0.9})
        assert result is False

    def test_handler_no_db_falls_back_to_event_params(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""), \
             patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", False), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", False), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", False):
            result = h.handler({"Q": 1.0, "nabla_phi": 0.0, "tau": 1.0}, None)
        assert "@context" in result
        assert "S" in result
        assert result["feeds_fresh"] is False

    def test_handler_with_live_db_uses_live_data(self):
        import beacon_core.lambdas.generate_status.handler as h
        live_data = {"S": 0.87, "delta_S": 0.01, "Q": 1.0, "tau": 0.95,
                     "nabla_phi": 0.02, "field_state": "stable"}
        with patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", False), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", False), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", False), \
             patch.object(h, "_fetch_live_telemetry", return_value=live_data):
            result = h.handler({}, None)
        assert result["feeds_fresh"] is True
        assert result["S"] == 0.87

    def test_handler_with_float_analytics_enabled(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""), \
             patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", False), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", True), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", False):
            result = h.handler({}, None)
        assert "S" in result

    def test_handler_payload_has_hash_and_context(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""), \
             patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", False), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", False), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", False):
            result = h.handler({}, None)
        assert "hash" in result
        assert "@context" in result

    def test_anchor_to_ledger_stub_creds_returns_none_none(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.IPFS_API_KEY", ""), \
             patch("identity_loop.zenodo.ipfs_pinner.IPFS_API_SECRET", ""), \
             patch("identity_loop.zenodo.zenodo_client.ZENODO_API_KEY", ""):
            cid, doi = h._anchor_to_ledger(payload)
        assert cid is None
        assert doi is None

    def test_anchor_to_ledger_ipfs_exception_returns_none_cid(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   side_effect=Exception("IPFS error")), \
             patch("identity_loop.zenodo.zenodo_client.ZENODO_API_KEY", ""):
            cid, doi = h._anchor_to_ledger(payload)
        assert cid is None

    def test_anchor_to_ledger_pinned_status_extracts_cid(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   return_value={"status": "pinned", "cid": "QmRealCID"}), \
             patch("identity_loop.zenodo.zenodo_client.ZENODO_API_KEY", ""):
            cid, doi = h._anchor_to_ledger(payload)
        assert cid == "QmRealCID"

    def test_anchor_to_ledger_ipfs_failed_status(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   return_value={"status": "error", "error": "timeout"}), \
             patch("identity_loop.zenodo.zenodo_client.ZENODO_API_KEY", ""):
            cid, doi = h._anchor_to_ledger(payload)
        assert cid is None

    def test_anchor_to_ledger_zenodo_published_extracts_doi(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   return_value={"status": "stub"}), \
             patch("identity_loop.zenodo.zenodo_client.deposit",
                   return_value={"status": "published", "doi": "10.5281/zenodo.123"}):
            cid, doi = h._anchor_to_ledger(payload)
        assert doi == "10.5281/zenodo.123"

    def test_anchor_to_ledger_zenodo_error_status(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   return_value={"status": "stub"}), \
             patch("identity_loop.zenodo.zenodo_client.deposit",
                   return_value={"status": "error", "error": "net"}):
            cid, doi = h._anchor_to_ledger(payload)
        assert doi is None

    def test_anchor_to_ledger_zenodo_exception(self):
        import beacon_core.lambdas.generate_status.handler as h
        payload = {"S": 0.9, "generated_at": 1234567890, "field_state": "stable"}
        with patch("identity_loop.zenodo.ipfs_pinner.pin_json",
                   return_value={"status": "stub"}), \
             patch("identity_loop.zenodo.zenodo_client.deposit",
                   side_effect=Exception("zenodo down")):
            cid, doi = h._anchor_to_ledger(payload)
        assert doi is None

    def test_handler_with_dns_update_enabled_exception_does_not_crash(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""), \
             patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", True), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", False), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", False), \
             patch("beacon_core.dns.godaddy_updater.update_dns_records",
                   side_effect=Exception("DNS error")):
            result = h.handler({}, None)
        assert "S" in result

    def test_handler_with_ledger_anchor_enabled(self):
        import beacon_core.lambdas.generate_status.handler as h
        with patch.object(h, "DATABASE_URL", ""), \
             patch.object(h, "S3_BUCKET", ""), \
             patch.object(h, "ENABLE_DNS_UPDATE", False), \
             patch.object(h, "ENABLE_FLOAT_ANALYTICS", False), \
             patch.object(h, "ENABLE_LEDGER_ANCHOR", True), \
             patch.object(h, "_anchor_to_ledger", return_value=(None, None)):
            result = h.handler({}, None)
        assert "S" in result
