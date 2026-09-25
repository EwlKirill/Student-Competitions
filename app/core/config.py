"""Application constants and configuration read from the environment.

Single source of truth for the name, tagline and description that appear on the page, in the
browser tab and in the test assertions — those are literals.

This module is the only place that reads the environment, for two things:

- `COMMIT_SHA` answers "which commit is live" (FR-025), resolved once at import time. See
  specs/002-public-deploy-cicd/data-model.md#1-configuration-read-from-the-environment.
- `resolve_database_url` decides where the database is, for both the application's startup and
  `migrations/env.py`, so the two always target the same database. It is a function rather than a
  constant because it creates the local data directory and may refuse to run. See
  specs/003-database-questions/contracts/configuration.md.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

APP_NAME = "Student Competitions"

APP_TAGLINE = "Online knowledge competitions for students."

APP_DESCRIPTION = (
    "Student Competitions is a web application for running online knowledge competitions in "
    "schools and universities. Teachers build a question bank and open a competition, students "
    "answer the questions in writing, and every answer is scored automatically."
)

APP_VERSION = "0.1.0"
"""The release number reported by `/healthz`. Equals `project.version` in `pyproject.toml`,
which `tests/unit/test_config.py` asserts."""

COMMIT_SHA = os.environ.get("APP_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"
"""The commit the running instance was built from.

`APP_COMMIT` (a local or CI `docker build --build-arg`) wins, then `RENDER_GIT_COMMIT` (set
automatically by Render for every deploy), then the literal `"unknown"`. `or` rather than a
default argument is deliberate: the Dockerfile declares `ARG APP_COMMIT=""`, so an unstamped
build sets the variable to an empty string, and empty must fall through rather than win.
"""


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
"""The directory that contains the `app` package: the repository root locally, `/app` in the
image. Anchored to the package rather than to the working directory, like the templates."""

DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "student_competitions.sqlite3"
"""The local database used when `DATABASE_URL` is not set and the app is not on Render (FR-002).
`data/` is git-ignored and excluded from the image's build context."""

SUPPORTED_SCHEMES = frozenset({"sqlite", "postgres", "postgresql", "postgresql+psycopg"})

POSTGRESQL_DRIVER = "postgresql+psycopg"
"""The one PostgreSQL driver installed (psycopg 3). Neon and CI hand out `postgresql://` URLs,
which SQLAlchemy would otherwise map to psycopg2, so they are rewritten to name it explicitly."""


class DatabaseConfigError(RuntimeError):
    """The database location is missing or unusable, so the application must not start.

    Its message never contains the URL or any part of it: the URL is a secret in production, and
    this message reaches the deploy log (FR-004, FR-032).
    """


def resolve_database_url(environ: Mapping[str, str] = os.environ) -> str:
    """Return the SQLAlchemy URL of the database, or raise `DatabaseConfigError`.

    First match wins:

    1. `DATABASE_URL` is set and non-empty: its scheme is checked, and `postgres://` or
       `postgresql://` is rewritten to `postgresql+psycopg://` with every other part preserved.
    2. `RENDER` is set: refuse. A production start without its database must fail the release,
       not silently serve from a throw-away file inside the container (FR-004).
    3. Otherwise the local SQLite file under `data/`, which is created if missing (FR-002).

    The guard keys on `RENDER` because Render is the recorded host. Moving to another host means
    adding that platform's always-set variable (for example `RAILWAY_ENVIRONMENT` or
    `FLY_APP_NAME`) to the guard, in the same pull request as the move.
    """
    raw = environ.get("DATABASE_URL", "")
    if raw:
        return _normalise(raw)
    if environ.get("RENDER"):
        raise DatabaseConfigError(
            "DATABASE_URL is required when running on Render; "
            "refusing to fall back to a local SQLite file."
        )
    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _normalise(raw: str) -> str:
    """Check the scheme of a configured URL and name the psycopg driver explicitly.

    Only the scheme is rewritten, as a string prefix: re-rendering the parsed URL would reorder
    the query string and re-quote the password, and the contract is that everything after the
    scheme is preserved exactly.

    Errors are raised `from None`: SQLAlchemy's own parse error quotes the URL, and chaining it
    would print the password in the traceback.
    """
    try:
        url = make_url(raw)
    except (ArgumentError, ValueError):
        raise DatabaseConfigError("DATABASE_URL is not a valid database URL.") from None
    scheme = url.drivername
    if scheme not in SUPPORTED_SCHEMES:
        raise DatabaseConfigError(
            f"DATABASE_URL uses unsupported scheme '{scheme}'; expected sqlite or postgresql."
        ) from None
    if scheme in {"postgres", "postgresql"}:
        return POSTGRESQL_DRIVER + raw[len(scheme) :]
    return raw
