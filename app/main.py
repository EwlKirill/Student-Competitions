"""FastAPI application construction: static mount, router registration, error handling.

The application takes no configuration — no environment variables, no database, no external
service is contacted at startup (FR-010).
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.core.config import APP_DESCRIPTION, APP_NAME
from app.core.templates import templates
from app.routers import pages

app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)


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
