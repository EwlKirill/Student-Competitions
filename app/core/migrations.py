"""Migration state: which revision the code expects, and which one the database is at.

Kept apart from `app.core.db` so the engine and session module stays free of Alembic. Used by
the startup guard in `app.main`, by the status line, and by the tests.

The Alembic configuration is anchored to the project root rather than to the working directory,
like the templates, so the answer is the same wherever the process is started from.
"""

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine

from app.core.config import PROJECT_ROOT

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

MIGRATION_LOCK_KEY = 3_003_202_609_240_001
"""Fixed 64-bit key of the PostgreSQL advisory lock `migrations/env.py` takes around every
upgrade. Any constant works, as long as it never changes and nothing else in the database uses
it. Defined here rather than in `env.py` so the concurrency test can hold the same lock."""


def alembic_config() -> Config:
    """The project's Alembic configuration, as the `alembic` command line reads it."""
    return Config(str(ALEMBIC_INI))


def head_revision() -> str:
    """The newest revision in `migrations/versions/`: the schema this code expects.

    Reads only the script directory; never connects to a database.
    """
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("migrations/versions/ contains no revision")
    return head


def current_revision(connection: Connection) -> str | None:
    """The revision recorded in the database's `alembic_version` table, or `None` when no
    migration has ever been applied to it."""
    return MigrationContext.configure(connection).get_current_revision()


def ensure_at_head(engine: Engine) -> str:
    """Return the database's revision if it equals head; otherwise refuse to start.

    Running against an older schema would fail on the first query that touches a new column, and
    running against a newer one means an older release is serving, so both fail fast with the
    command that fixes the usual cause. The message names revisions only, never the database URL.
    """
    expected = head_revision()
    with engine.connect() as connection:
        current = current_revision(connection)
    if current != expected:
        raise RuntimeError(
            f"Database is at revision {current or 'none'} but the code expects {expected} — "
            "run `uv run alembic upgrade head`."
        )
    return current
