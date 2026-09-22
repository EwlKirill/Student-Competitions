"""The shared Jinja2 environment.

Lives in `core/` rather than in `app.main`: `app.main` imports the routers, so a router importing
`templates` back from `app.main` would close an import cycle and fail at startup. Every router,
the error handler and every later milestone share this one instance.

The directory is anchored to this package rather than to the working directory, so the
application serves the same templates whether it is started from the repository root, from `/app`
in the container, or from anywhere else (FR-011, research D14).
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
