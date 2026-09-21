"""The shared Jinja2 environment.

Lives in `core/` rather than in `app.main`: `app.main` imports the routers, so a router importing
`templates` back from `app.main` would close an import cycle and fail at startup. Every router,
the error handler and every later milestone share this one instance.
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
