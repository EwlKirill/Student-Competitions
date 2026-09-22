"""Service status: liveness and the running version, for machines rather than people.

Three consumers: Render's health check (`healthCheckPath` in `render.yaml`), the deploy
pipeline's post-release verification (`scripts/wait_for_release.sh`), and a human asking what is
live right now. See specs/002-public-deploy-cicd/contracts/http-routes.md.
"""

import os

from fastapi import APIRouter

from app.core.config import APP_VERSION, COMMIT_SHA

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Report that the process is serving, and which release it is.

    Performs **no I/O of any kind** — no database, no file read, no outbound request. Render's
    health check must get a 2xx inside 5 seconds, and an endpoint that can be slow is an endpoint
    that can take the service down.

    A plain dict rather than a Pydantic schema: `app/schemas/` is reserved for request/response
    and LLM structured-output models, and a three-key literal with no input and no variation has
    nothing for a schema to do (data-model.md §2).
    """
    return {"status": "ok", "version": APP_VERSION, "commit": COMMIT_SHA}
