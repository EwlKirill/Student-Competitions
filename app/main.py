"""FastAPI application construction: startup, static mount, router registration, error handling.

Startup needs a database at the schema this code expects. The `lifespan` resolves its location,
refuses to run against a database that is not at the newest migration, and only then lets
uvicorn open the port, so an instance that answers `/healthz` at all has a usable database. On
Render that makes a misconfigured or unmigrated release fail its deploy while the previous one
keeps serving (specs/003-database-questions/contracts/http-routes.md, "Application startup").
Migrations themselves are applied by the container entrypoint, not here.

Paths are anchored to this package rather than to the working directory, so the application
serves the same files wherever it is started from (FR-011, research D14).
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.exceptions import HTTPException

from app.core.config import APP_DESCRIPTION, APP_NAME, resolve_database_url
from app.core.db import create_db_engine
from app.core.migrations import ensure_at_head
from app.core.templates import templates
from app.routers import health, pages
from app.services.database_status import record_boot

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Uvicorn's general-purpose logger (the name is historical), configured at INFO, so the startup
# line appears next to uvicorn's own "Application startup complete".
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect to the database, refuse to start unless it is at head, and count this start.

    Any failure propagates: uvicorn exits non-zero before binding the port, so a start that was
    refused is never counted. The log line names the engine, the revision and the boot number
    only — never the URL, which is a secret in production.
    """
    engine = create_db_engine(resolve_database_url(os.environ))
    try:
        revision = ensure_at_head(engine)
        with Session(engine) as session:
            boots = record_boot(session)
        app.state.engine = engine
        logger.info(
            "Database: %s at schema revision %s, boot #%d", engine.dialect.name, revision, boots
        )
        yield
    finally:
        engine.dispose()


app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(health.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Render a friendly page for any HTTP error, never a stack trace or raw JSON.

    Registered for `HTTPException` in general rather than only 404, so routes added in later
    milestones inherit the same page.
    """
    return templates.TemplateResponse(
        request,
        "pages/error.html",
        {
            "app_name": APP_NAME,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
        status_code=exc.status_code,
    )
