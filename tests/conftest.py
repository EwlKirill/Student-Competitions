"""Shared test fixtures: every database test runs on SQLite and on PostgreSQL.

`database_url` is parametrized over both engines, so any test that uses it — directly, or through
`engine`, `session` or `client` — runs twice, as `[sqlite]` and `[postgresql]` (FR-030). Each test
gets its own clone of a database migrated to head once per session **with Alembic**, so every run
also exercises the migrations, and no test sees another's writes.

PostgreSQL comes from `TEST_POSTGRES_URL`, a server whose role may `CREATE DATABASE`. It is never
`DATABASE_URL`, so a test can never reach a developer's data or production (FR-031). Without it
the PostgreSQL cases are skipped locally; under `CI=true` the session refuses to start.

See specs/003-database-questions/research.md#d12.
"""

import itertools
import os
import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from app.core.config import resolve_database_url
from app.core.db import create_db_engine
from app.core.migrations import alembic_config
from app.main import app

ENGINES = ["sqlite", "postgresql"]

POSTGRES_SKIP_REASON = "set TEST_POSTGRES_URL to run the PostgreSQL cases (see README)"

RUN_TOKEN = secrets.token_hex(4)
"""In every PostgreSQL database name, so parallel or repeated runs against one server never
collide, and a leftover from a crashed run is recognisable."""

_database_numbers = itertools.count(1)


def pytest_sessionstart(session: pytest.Session) -> None:
    """CI must run both halves of the matrix; skipping PostgreSQL there would go green on half."""
    if os.environ.get("CI") == "true" and not os.environ.get("TEST_POSTGRES_URL"):
        pytest.exit(
            "CI=true but TEST_POSTGRES_URL is not set: the PostgreSQL half of the suite would be "
            "skipped. Configure the postgres service in the workflow.",
            returncode=1,
        )


@pytest.fixture(autouse=True)
def _isolate_from_real_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test inherits a developer's `DATABASE_URL` or a `RENDER` flag from the shell."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


# ---------------------------------------------------------------------------------------------
# Migrations and servers
# ---------------------------------------------------------------------------------------------


def migrate(database_url: str, target: str = "head") -> None:
    """Run `alembic upgrade <target>` against `database_url`, exactly as the entrypoint does."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", database_url)
        command.upgrade(alembic_config(), target)


def _postgres_admin_url() -> str:
    raw = os.environ.get("TEST_POSTGRES_URL")
    if not raw:
        pytest.skip(POSTGRES_SKIP_REASON)
    return resolve_database_url({"DATABASE_URL": raw})


def _postgres_database_url(admin_url: str, name: str) -> str:
    return make_url(admin_url).set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def _postgres_admin() -> Iterator[tuple[str, Engine]]:
    """An `AUTOCOMMIT` engine on the test server: `CREATE`/`DROP DATABASE` cannot run in a
    transaction."""
    url = _postgres_admin_url()
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    yield url, engine
    engine.dispose()


def _create_postgres_database(admin: tuple[str, Engine], name: str, template: str | None) -> str:
    admin_url, engine = admin
    statement = f'CREATE DATABASE "{name}"'
    if template is not None:
        statement += f' TEMPLATE "{template}"'
    with engine.connect() as connection:
        connection.execute(text(statement))
    return _postgres_database_url(admin_url, name)


def _drop_postgres_database(admin: tuple[str, Engine], name: str) -> None:
    with admin[1].connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


# ---------------------------------------------------------------------------------------------
# Templates: one migrated database per engine per session
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _sqlite_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("sqlite-template") / "template.sqlite3"
    migrate(f"sqlite:///{path}")
    return path


@pytest.fixture(scope="session")
def _postgres_template(_postgres_admin: tuple[str, Engine]) -> Iterator[str]:
    name = f"sc_test_{RUN_TOKEN}_template"
    migrate(_create_postgres_database(_postgres_admin, name, template=None))
    yield name
    _drop_postgres_database(_postgres_admin, name)


# ---------------------------------------------------------------------------------------------
# Per-test databases
# ---------------------------------------------------------------------------------------------


@pytest.fixture(params=ENGINES, ids=ENGINES)
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    """A private database at head, as the migrations leave it: samples present, `boots = 0`.

    The yielded URL is in the form the application uses (`postgresql+psycopg://`).
    """
    if request.param == "sqlite":
        template: Path = request.getfixturevalue("_sqlite_template")
        clone = tmp_path / "test.sqlite3"
        shutil.copy(template, clone)
        yield f"sqlite:///{clone}"
        return
    admin = request.getfixturevalue("_postgres_admin")
    template_name = request.getfixturevalue("_postgres_template")
    name = f"sc_test_{RUN_TOKEN}_{next(_database_numbers)}"
    yield _create_postgres_database(admin, name, template=template_name)
    _drop_postgres_database(admin, name)


@pytest.fixture(params=ENGINES, ids=ENGINES)
def empty_database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    """A database with no migration applied, for the startup and migration tests."""
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'empty.sqlite3'}"
        return
    admin = request.getfixturevalue("_postgres_admin")
    name = f"sc_test_{RUN_TOKEN}_{next(_database_numbers)}_empty"
    yield _create_postgres_database(admin, name, template=None)
    _drop_postgres_database(admin, name)


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    db_engine = create_db_engine(database_url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[TestClient]:
    """Drive the real ASGI application in-process — no live server, no bound port.

    The database is given the way production gives it, through `DATABASE_URL`, so `lifespan`
    resolves, guards and counts the start exactly as it does on Render.
    """
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_questions() -> list[dict[str, Any]]:
    """The seeded sample questions, read from the migration that inserts them.

    The migration is the single source of truth; tests never keep a copy that could drift
    (research D6).
    """
    script = ScriptDirectory.from_config(alembic_config())
    for revision in script.walk_revisions():
        samples = getattr(revision.module, "SAMPLE_QUESTIONS", None)
        if samples is not None:
            return samples
    raise LookupError("no revision in migrations/versions/ defines SAMPLE_QUESTIONS")
