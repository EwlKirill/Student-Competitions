"""Database infrastructure shared by every model and request: engine, session, UTC timestamps.

Kept free of Alembic imports; migration state lives in `app.core.migrations`. The engine is
created once per application start by the `lifespan` in `app.main` and stored on
`app.state.engine`, so tests can point each application instance at its own database.

See specs/003-database-questions/research.md#d8 (timestamps) and #d10 (engine settings).
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import DateTime, Engine, create_engine
from sqlalchemy.engine import Dialect, make_url
from sqlalchemy.types import TypeDecorator
from sqlmodel import Session, SQLModel

# Constraint and index names are generated from one convention, so they are identical on
# SQLite and PostgreSQL and later SQLite batch migrations can find them by name (research D14).
# Set at import time, before any table model is defined against this metadata.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp that is timezone-aware UTC on the way in and on the way out, on both engines.

    PostgreSQL's `timestamptz` keeps the instant but returns it in the session's time zone;
    SQLite keeps no offset at all and returns a naive value. Without this type the same query
    returns different values locally and in production (FR-006).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime refuses a naive datetime; use app.core.db.utc_now()")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utc_now() -> datetime:
    """The current time, timezone-aware UTC. The one clock every stored timestamp comes from, so
    tests can control it."""
    return datetime.now(UTC)


def create_db_engine(url: str) -> Engine:
    """Create the engine for `url` (already resolved by `resolve_database_url`).

    - `pool_pre_ping`: Neon closes idle connections when its compute suspends; a stale pooled
      connection is replaced instead of failing the request.
    - `hide_parameters`: bound values never appear in error messages or logs.
    - SQLite `check_same_thread=False`: FastAPI runs sync handlers in a thread pool, so a pooled
      connection may be used by a different thread than the one that opened it.
    - PostgreSQL `connect_timeout=5`: an unreachable database fails the page within seconds
      instead of hanging it.
    """
    connect_args: dict[str, Any]
    if make_url(url).get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {"connect_timeout": 5}
    return create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=connect_args)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, on the engine the application started with."""
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
"""A request's session, for a handler's signature: `def page(session: SessionDep)`."""
