"""Alembic environment (sync engine for migrations)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from database.db import database_url_sync
from database.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Build the synchronous psycopg database URL used by Alembic.

    Returns:
        Normalized PostgreSQL connection URL for migration operations.
    """
    return database_url_sync(os.environ.get("DATABASE_URL"))


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection.

    Literal binds are enabled so the resulting SQL can be executed separately.

    Returns:
        None.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply pending migrations through a synchronous database connection.

    A short-lived engine and transaction are used for Alembic operations.

    Returns:
        None.
    """
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
