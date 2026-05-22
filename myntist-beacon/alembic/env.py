"""Alembic migration environment for myntist-beacon."""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the myntist-beacon package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from iam_substrate.substrate_api.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://myntist:myntist@localhost:5432/myntist_beacon",
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL only, no live connection."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = DATABASE_URL
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
