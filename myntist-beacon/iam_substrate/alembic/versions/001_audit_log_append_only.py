"""Add append-only triggers to iam_substrate_log table

Revision ID: 001
Revises:
Create Date: 2026-05-07

Installs the deny_audit_mutation trigger function and two separate BEFORE triggers
(one for UPDATE, one for DELETE) on the iam_substrate_log table, enforcing the
tamper-evident append-only property of the sovereign audit trail.

Also revokes UPDATE and DELETE privileges from the application role ('myntist')
as a defence-in-depth measure.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the shared trigger function
    op.execute("""
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
        $$
    """)

    # BEFORE UPDATE trigger (idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM   pg_trigger
                WHERE  tgname  = 'trg_audit_no_update'
                  AND  tgrelid = 'iam_substrate_log'::regclass
            ) THEN
                CREATE TRIGGER trg_audit_no_update
                BEFORE UPDATE
                ON iam_substrate_log
                FOR EACH ROW
                EXECUTE FUNCTION deny_audit_mutation();
            END IF;
        END;
        $$
    """)

    # BEFORE DELETE trigger (idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM   pg_trigger
                WHERE  tgname  = 'trg_audit_no_delete'
                  AND  tgrelid = 'iam_substrate_log'::regclass
            ) THEN
                CREATE TRIGGER trg_audit_no_delete
                BEFORE DELETE
                ON iam_substrate_log
                FOR EACH ROW
                EXECUTE FUNCTION deny_audit_mutation();
            END IF;
        END;
        $$
    """)

    # Defence-in-depth: revoke destructive DML from the application role
    op.execute("REVOKE UPDATE, DELETE ON iam_substrate_log FROM myntist")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_audit_no_update ON iam_substrate_log"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_audit_no_delete ON iam_substrate_log"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS deny_audit_mutation()"
    )
    op.execute("GRANT UPDATE, DELETE ON iam_substrate_log TO myntist")
