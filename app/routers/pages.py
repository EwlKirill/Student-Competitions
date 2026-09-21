"""Server-rendered pages. Thin handlers only — application wiring lives in `app.main`."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import APP_DESCRIPTION, APP_NAME, APP_TAGLINE
from app.core.templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the home page."""
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "app_name": APP_NAME,
            "app_tagline": APP_TAGLINE,
            "app_description": APP_DESCRIPTION,
        },
    )
