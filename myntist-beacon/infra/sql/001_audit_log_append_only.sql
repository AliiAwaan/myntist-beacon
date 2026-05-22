-- Migration: 001_audit_log_append_only
-- Purpose:   Make iam_substrate_log append-only by blocking UPDATE and DELETE
--            via two separate BEFORE triggers. This enforces the tamper-evident
--            property of the sovereign audit trail — rows may only be inserted,
--            never modified or removed.
--
-- Apply:     psql $DATABASE_URL -f infra/sql/001_audit_log_append_only.sql
-- Rollback:  DROP TRIGGER trg_audit_no_update ON iam_substrate_log;
--            DROP TRIGGER trg_audit_no_delete ON iam_substrate_log;
--            DROP FUNCTION deny_audit_mutation();
-- Idempotent: Yes — OR REPLACE + IF NOT EXISTS guards.

-- ── Step 1: trigger function ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION deny_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'iam_substrate_log is append-only: % operations are not permitted (row id=%)',
        TG_OP,
        COALESCE(OLD.id::text, '?');
    RETURN NULL;
END;
$$;

-- ── Step 2: BEFORE UPDATE trigger ───────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   pg_trigger
        WHERE  tgname   = 'trg_audit_no_update'
          AND  tgrelid  = 'iam_substrate_log'::regclass
    ) THEN
        CREATE TRIGGER trg_audit_no_update
        BEFORE UPDATE
        ON iam_substrate_log
        FOR EACH ROW
        EXECUTE FUNCTION deny_audit_mutation();
    END IF;
END;
$$;

-- ── Step 3: BEFORE DELETE trigger ───────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   pg_trigger
        WHERE  tgname   = 'trg_audit_no_delete'
          AND  tgrelid  = 'iam_substrate_log'::regclass
    ) THEN
        CREATE TRIGGER trg_audit_no_delete
        BEFORE DELETE
        ON iam_substrate_log
        FOR EACH ROW
        EXECUTE FUNCTION deny_audit_mutation();
    END IF;
END;
$$;

-- ── Step 4: revoke DML privileges from the application role ─────────────────
-- Defence-in-depth: even a compromised app process cannot bypass the triggers.

REVOKE UPDATE, DELETE ON iam_substrate_log FROM myntist;

-- ── Verify ───────────────────────────────────────────────────────────────────
-- Run after applying to confirm both triggers are installed:
--
--   SELECT tgname, tgenabled
--   FROM   pg_trigger
--   WHERE  tgrelid = 'iam_substrate_log'::regclass;
--
-- Expected output:
--   tgname               | tgenabled
--   trg_audit_no_update  | O
--   trg_audit_no_delete  | O
