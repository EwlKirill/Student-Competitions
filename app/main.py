"""FastAPI application construction: static mount, router registration, error handling.

The application starts with no required configuration — no database and no external service is
contacted at startup (FR-010). The only environment values it reads are the optional commit
stamps in `app.core.config`, which `/healthz` reports.

Paths are anchored to this package rather than to the working directory, so the application
serves the same files wherever it is started from (FR-011, research D14).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.core.config import APP_DESCRIPTION, APP_NAME
from app.core.templates import templates
from app.routers import health, pages

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION)

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
