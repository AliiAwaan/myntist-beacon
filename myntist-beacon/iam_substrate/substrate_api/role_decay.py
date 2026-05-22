"""
Role decay scheduler — runs every 60 seconds.

For any identity where S < 0.7: flags for remediation and calls autoheal.

Also runs a live telemetry emitter every 12 seconds so the dashboard always
has fresh, up-to-date records regardless of external event traffic.

Environment variables:
  TELEMETRY_BATCH_LIMIT      — max identities processed per live-telemetry
                               cycle (default: 50)
  TELEMETRY_RETENTION_HOURS  — delete telemetry rows older than this many
                               hours (default: 24); set to 0 to disable pruning
"""
from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
_scheduler_started = False


def check_and_heal() -> None:
    """Scheduled job: scan all identities and autoheal those with S < 0.7."""
    from .autoheal import run_autoheal
    from .database import get_session_local
    from .models import Identity

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        identities = db.query(Identity).all()
        flagged = [
            {"id": identity.id, "S": identity.S, "field_state": identity.field_state}
            for identity in identities
            if identity.S < 0.7
        ]
        if flagged:
            logger.info("Role decay: %d identities flagged for autoheal", len(flagged))
            run_autoheal(flagged, db=db)
        else:
            logger.debug("Role decay check: all identities healthy")
    except Exception as exc:
        logger.error("Role decay check failed: %s", exc)
    finally:
        db.close()


def _int_env(name: str, default: int, min_val: int | None = None) -> int:
    """Read an integer environment variable, falling back to *default*.

    If *min_val* is given the returned value is clamped to at least that
    bound.  A warning is logged whenever the raw env value is invalid or
    below the minimum.
    """
    raw = os.environ.get(name, "")
    value = default
    if raw:
        try:
            parsed = int(raw)
            if min_val is not None and parsed < min_val:
                logger.warning(
                    "%s=%r is below minimum %d; using %d instead",
                    name, raw, min_val, min_val,
                )
                parsed = min_val
            value = parsed
        except (ValueError, TypeError):
            logger.warning(
                "%s=%r is not a valid integer; using default %d",
                name, raw, default,
            )
    return value


_TELEMETRY_BATCH_LIMIT: int = _int_env("TELEMETRY_BATCH_LIMIT", 50, min_val=1)
_TELEMETRY_RETENTION_HOURS: int = _int_env("TELEMETRY_RETENTION_HOURS", 24)

_telemetry_cursor = 0  # round-robin offset; advances each cycle


def emit_live_telemetry() -> None:
    """
    Scheduled job: emit a fresh telemetry record every 12 seconds so the
    dashboard always shows current timestamps even when no external events
    are arriving.

    Round-robin pagination ensures every registered identity receives a
    heartbeat over successive cycles, even when the total identity count
    exceeds _TELEMETRY_BATCH_LIMIT.

    Ordering is stable (created_at ASC, id ASC) so the offset is consistent
    across calls. The cursor advances by _TELEMETRY_BATCH_LIMIT each cycle
    and resets to 0 once the end of the set is reached.

    Falls back to a single 'system' record when no identities exist yet.

    Also appends an audit entry per identity per cycle so that the
    iam_substrate_log receives entries continuously, not only on
    POST /events (which requires an HMAC-signed external caller).
    """
    global _telemetry_cursor

    from .database import get_session_local
    from .models import Identity
    from .scoring import score_from_inputs
    from .telemetry_emitter import emit_telemetry
    from iam_substrate.ledger.audit_log import append_audit_entry

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        total = db.query(Identity).count()

        if total == 0:
            # No identities registered yet — emit a system heartbeat so the
            # dashboard always has something to display.
            _telemetry_cursor = 0
            Q = max(0.01, min(2.0, 1.0 + random.gauss(0, 0.02)))
            tau = max(0.01, min(1.0, 1.0 + random.gauss(0, 0.005)))
            nabla_phi = max(0.0, min(0.5, 0.0 + random.gauss(0, 0.002)))
            result = score_from_inputs(Q, nabla_phi, tau)
            emit_telemetry(
                db=db,
                identity_id="system",
                S=result.S,
                delta_S=result.delta_S,
                Q=Q,
                tau=tau,
                nabla_phi=nabla_phi,
                field_state=result.field_state,
            )
            try:
                append_audit_entry(
                    db=db,
                    identity_id="system",
                    event_type="heartbeat",
                    action=f"system heartbeat: S={result.S:.4f} field_state={result.field_state}",
                    S_after=result.S,
                )
            except Exception as audit_exc:
                logger.warning("audit entry failed (system heartbeat): %s", audit_exc)
            logger.debug("Live telemetry emitted: identity=system (no identities registered)")
            return

        # Ensure cursor is within bounds after any external identity deletions.
        _telemetry_cursor = _telemetry_cursor % total

        identities = (
            db.query(Identity)
            .order_by(Identity.created_at.asc(), Identity.id.asc())
            .offset(_telemetry_cursor)
            .limit(_TELEMETRY_BATCH_LIMIT)
            .all()
        )

        for identity in identities:
            base_Q = float(identity.Q or 1.0)
            base_tau = float(identity.tau or 1.0)
            base_nabla_phi = float(identity.nabla_phi or 0.0)

            Q = max(0.01, min(2.0, base_Q + random.gauss(0, 0.02)))
            tau = max(0.01, min(1.0, base_tau + random.gauss(0, 0.005)))
            nabla_phi = max(0.0, min(0.5, base_nabla_phi + random.gauss(0, 0.002)))

            result = score_from_inputs(Q, nabla_phi, tau)
            old_S = float(identity.S or result.S)
            delta_S = result.S - old_S

            emit_telemetry(
                db=db,
                identity_id=identity.id,
                S=result.S,
                delta_S=delta_S,
                Q=Q,
                tau=tau,
                nabla_phi=nabla_phi,
                field_state=result.field_state,
            )
            try:
                append_audit_entry(
                    db=db,
                    identity_id=identity.id,
                    event_type="heartbeat",
                    action=f"heartbeat: S={result.S:.4f} field_state={result.field_state}",
                    S_before=old_S,
                    S_after=result.S,
                )
            except Exception as audit_exc:
                logger.warning(
                    "audit entry failed (heartbeat identity=%s): %s",
                    identity.id, audit_exc,
                )
            logger.debug(
                "Live telemetry emitted: identity=%s S=%.4f field_state=%s",
                identity.id, result.S, result.field_state,
            )

        # Advance cursor with modulo wrapping so we never land on an empty offset.
        _telemetry_cursor = (_telemetry_cursor + len(identities)) % total

        logger.info(
            "Live telemetry cycle complete: %d/%d identities updated, next cursor=%d",
            len(identities), total, _telemetry_cursor,
        )
    except Exception as exc:
        logger.error("emit_live_telemetry failed: %s", exc)
    finally:
        db.close()


def prune_telemetry() -> None:
    """
    Scheduled job: delete telemetry rows older than _TELEMETRY_RETENTION_HOURS.

    Runs every 60 seconds alongside the role-decay check.  The retention
    window is read once at startup from the TELEMETRY_RETENTION_HOURS env var
    (default 24 h).  Set the var to 0 to disable pruning entirely.
    """
    if _TELEMETRY_RETENTION_HOURS <= 0:
        return

    from .database import get_session_local
    from .models import TelemetryRecord

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_TELEMETRY_RETENTION_HOURS)
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        deleted = (
            db.query(TelemetryRecord)
            .filter(TelemetryRecord.recorded_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logger.info(
                "Telemetry pruned: %d rows older than %d h removed",
                deleted,
                _TELEMETRY_RETENTION_HOURS,
            )
        else:
            logger.debug("Telemetry pruned: no rows older than %d h", _TELEMETRY_RETENTION_HOURS)
    except Exception as exc:
        logger.error("prune_telemetry failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def run_float_ledger() -> None:
    """Monthly scheduled job: generate float ledger CSV + JSON summary to S3 or /tmp."""
    try:
        from beacon_core.lambdas.generate_float_ledger.handler import handler
        result = handler({}, None)
        logger.info("Float ledger job complete: csv=%s", result.get("csv_location"))
    except Exception as exc:
        logger.error("run_float_ledger failed: %s", exc)


def run_parquet_export() -> None:
    """Weekly scheduled job: export field_telemetry to Parquet (snappy) to S3 or /tmp."""
    try:
        from beacon_core.lambdas.export_parquet.handler import handler
        result = handler({}, None)
        logger.info(
            "Parquet export job complete: records=%s dest=%s",
            result.get("record_count"),
            result.get("parquet_location"),
        )
    except Exception as exc:
        logger.error("run_parquet_export failed: %s", exc)


def _run_key_age_check() -> None:
    """
    Daily scheduled job: delegate key-age verification to kcp.rotation_handler.

    Calls kcp.rotation_handler.check_key_age() which reads ED25519_KEY_CREATED
    from the environment and warns when the key is older than KEY_MAX_AGE_DAYS
    (default 330 days). Failure is caught and logged so it never crashes the
    scheduler loop.
    """
    try:
        from kcp.rotation_handler import check_key_age
        check_key_age()
    except Exception as exc:
        logger.error("_run_key_age_check failed: %s", exc)


def start_scheduler() -> None:
    """Start the APScheduler background job."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler.add_job(check_and_heal, "interval", seconds=60, id="role_decay")
    # Publication cadence: live telemetry at 12 s matches the dashboard POLL_INTERVAL_MS
    # (12 000 ms) so every poll cycle sees a fresh DB row. The 60 s spec minimum is the
    # floor for role-decay healing — telemetry is intentionally more frequent to keep
    # the Beacon status panel accurate between external event arrivals.
    _scheduler.add_job(emit_live_telemetry, "interval", seconds=12, id="live_telemetry")
    _scheduler.add_job(prune_telemetry, "interval", seconds=60, id="telemetry_pruner")
    # Monthly float ledger: 1st of each month at 00:00 UTC
    _scheduler.add_job(
        run_float_ledger, "cron", day=1, hour=0, minute=0, id="float_ledger",
    )
    # Weekly parquet export: every Sunday at 00:00 UTC
    _scheduler.add_job(
        run_parquet_export, "cron", day_of_week="sun", hour=0, minute=0, id="parquet_export",
    )
    # Daily key-age check: every 24 hours (delegates to kcp.rotation_handler)
    _scheduler.add_job(
        _run_key_age_check, "interval", hours=24, id="key_age_check",
    )
    _scheduler.start()
    _scheduler_started = True
    logger.info("Role decay scheduler started (60s interval)")
    logger.info("Live telemetry emitter started (12s interval, matches dashboard POLL_INTERVAL_MS)")
    logger.info(
        "Telemetry pruner started (60s interval, retention=%d h)",
        _TELEMETRY_RETENTION_HOURS,
    )
    logger.info("Float ledger job scheduled (monthly cron: 1st 00:00 UTC)")
    logger.info("Parquet export job scheduled (weekly cron: Sunday 00:00 UTC)")
    logger.info("Key age check job scheduled (24h interval, via kcp.rotation_handler)")


def stop_scheduler() -> None:
    """Stop the scheduler (call on app shutdown)."""
    global _scheduler_started
    if _scheduler_started:
        _scheduler.shutdown(wait=False)
        _scheduler_started = False


def get_flagged_identities(db) -> List[dict]:
    """Return identities with S < 0.7 without triggering autoheal."""
    from .models import Identity
    identities = db.query(Identity).all()
    return [
        {"id": i.id, "S": i.S, "field_state": i.field_state}
        for i in identities
        if i.S < 0.7
    ]
