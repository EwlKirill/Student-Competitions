"""Application startup: the effective readiness gate.

The application refuses to start without a usable database at head, so an instance that answers
at all has one. See specs/003-database-questions/contracts/http-routes.md#application-startup-
the-effective-readiness-gate.
"""

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.core.config as config
from app.core.db import create_db_engine
from app.core.migrations import alembic_config, head_revision
from app.main import app
from app.services.database_status import read_database_status
from tests.conftest import migrate


def test_refuses_to_start_on_an_unmigrated_database(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", empty_database_url)
    with pytest.raises(RuntimeError) as caught, TestClient(app):
        pass
    message = str(caught.value)
    assert "uv run alembic upgrade head" in message
    assert empty_database_url not in message


def test_refuses_to_start_on_render_without_a_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER", "true")
    with (
        pytest.raises(config.DatabaseConfigError, match="DATABASE_URL is required"),
        TestClient(app),
    ):
        pass


def _revision_before_head() -> str:
    previous = ScriptDirectory.from_config(alembic_config()).get_revision(head_revision())
    assert previous is not None and isinstance(previous.down_revision, str)
    return previous.down_revision


def _boots(database_url: str) -> int:
    engine = create_db_engine(database_url)
    try:
        with Session(engine) as session:
            return read_database_status(session).boots
    finally:
        engine.dispose()


def test_a_refused_start_behind_head_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str
) -> None:
    """A database one revision behind head: the tables exist, but the start is refused."""
    migrate(empty_database_url, _revision_before_head())
    monkeypatch.setenv("DATABASE_URL", empty_database_url)
    with pytest.raises(RuntimeError, match="uv run alembic upgrade head"), TestClient(app):
        pass
    assert _boots(empty_database_url) == 0


def test_a_refused_start_on_render_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """`RENDER` without `DATABASE_URL` never reaches this database; its count stays at zero."""
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(config.DatabaseConfigError), TestClient(app):
        pass
    assert _boots(database_url) == 0
