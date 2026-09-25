"""Alembic environment: runs the migrations against the database the application uses.

The URL comes from `resolve_database_url`, the same function the application's startup calls, so
the two can never target different databases. It is used to build the engine directly and is
never written into the Alembic config, where it would be `%`-interpolated and could be logged.

See specs/003-database-questions/research.md#d3, #d5 and #d14.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models  # noqa: F401 — registers every table on SQLModel.metadata
from app.core.config import resolve_database_url
from app.core.migrations import MIGRATION_LOCK_KEY

config = context.config

# `disable_existing_loggers=False`: the tests and the startup guard use Alembic in-process, and
# the default would silence every logger the application had already created.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    """Run every pending migration on one connection.

    On PostgreSQL the whole upgrade is one transaction (`transaction_per_migration` stays False),
    so a failure anywhere rolls back every revision and the database stays at its previous
    revision (FR-010). SQLite has no transactional DDL; a failed local migration is fixed and
    re-run, or the local file deleted.
    """
    engine = create_engine(resolve_database_url(os.environ), poolclass=NullPool)
    with engine.connect() as connection:
        dialect = connection.dialect.name
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite cannot ALTER most things in place; batch mode copies the table instead.
            render_as_batch=dialect == "sqlite",
        )
        with context.begin_transaction():
            if dialect == "postgresql":
                # Principle VII's one PostgreSQL-specific feature, justified in the plan's
                # Complexity Tracking: during a Render deploy two instances can start at once,
                # and without serialisation both would run the same revisions, so the loser
                # fails on CREATE TABLE or applies a data migration twice. The lock is
                # transaction-scoped, so it is released on commit, rollback or a crash, and it is
                # taken before Alembic reads the current revision, so the second instance sees
                # the first one's result and has nothing to do. SQLite needs no equivalent: it is
                # local and single-process, and its database-level write lock serialises writers.
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
                )
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) migrations are not supported; run against a database.")
run_migrations_online()
