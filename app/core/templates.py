"""The shared Jinja2 environment.

Lives in `core/` rather than in `app.main`: `app.main` imports the routers, so a router importing
`templates` back from `app.main` would close an import cycle and fail at startup. Every router,
the error handler and every later milestone share this one instance.

The directory is anchored to this package rather than to the working directory, so the
application serves the same templates whether it is started from the repository root, from `/app`
in the container, or from anywhere else (FR-011, research D14).

The release identity is registered as a Jinja global rather than passed by each handler: the
footer in the shared layout is rendered by every page, including the error page, and a value
every template needs belongs to the environment rather than to each handler's context.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.config import APP_VERSION, COMMIT_SHA

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

SHORT_COMMIT_LENGTH = 7
"""Enough to identify a commit by eye and to paste into `git show`; the full value stays in the
footer's `title` attribute and in `/healthz`."""

templates = Jinja2Templates(directory=TEMPLATES_DIR)

templates.env.globals["app_version"] = APP_VERSION
templates.env.globals["commit_sha"] = COMMIT_SHA
templates.env.globals["commit_short"] = COMMIT_SHA[:SHORT_COMMIT_LENGTH]
