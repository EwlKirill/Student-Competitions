# Container Contract: image, entrypoint and environment

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](../plan.md)

What the packaged application promises, independent of who runs it — a developer with
`docker run`, the CI `image` job, or Render (FR-008, FR-009, FR-010, FR-011). Design rationale:
[research.md D5](../research.md#d5--image-design) and [D6](../research.md#d6--runtime-configuration).

## Build

| Aspect | Contract |
|---|---|
| Context | Repository root; `.dockerignore` excludes `.git/`, `.venv/`, `tests/`, `specs/`, `docs/`, `.github/`, `__pycache__/`, caches, editor and environment files |
| File | `./Dockerfile`, two stages |
| Builder stage | `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`; copies **only** `pyproject.toml` + `uv.lock`, then `uv sync --locked --no-dev --no-install-project` → `/app/.venv` |
| Runtime stage | `python:3.13-slim-bookworm`; receives `/app/.venv` and `app/` and nothing else — no uv, no compiler, no tests, no VCS metadata |
| Build args | `APP_COMMIT` (default `""`) — stamps the commit for local and CI builds |
| Reproducibility | `--locked` fails the build if `uv.lock` does not match `pyproject.toml`; base images pinned to the exact Python minor version and Debian release (FR-018, FR-008) |
| Build must succeed with | no network access to anything but the package index and the base images; **no secrets** — the build takes no credential and none may ever be added (FR-027) |

## Runtime

| Aspect | Contract |
|---|---|
| User | Non-root |
| Working directory | `/app`, with the application importable as `app` |
| Listening address | `${HOST:-0.0.0.0}:${PORT:-8000}` |
| Entrypoint | `CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]` — `sh -c` so `${PORT}` expands, **`exec`** so uvicorn is PID 1 and receives `SIGTERM` directly |
| Shutdown | On `SIGTERM`, uvicorn stops accepting connections, finishes in-flight requests and exits; it must not require `SIGKILL` (this is what `exec` buys, and what makes a redeploy clean) |
| Filesystem | Read-only in practice — the application writes nothing at runtime, so the platform's ephemeral disk is irrelevant |
| Docker `HEALTHCHECK` | `python -c` request to `/healthz` (no `curl` in the image). Used by `docker run` and the CI smoke test; Render uses `healthCheckPath` instead |
| Exposed port | `8000` (documentation only — the real port comes from `$PORT`) |

## Environment variables

The complete configuration surface. This table is the source for the README's variable table
(FR-012) and must stay in step with it.

| Variable | Read by | Required | Default | Purpose |
|---|---|---|---|---|
| `PORT` | entrypoint → `uvicorn --port` | no | `8000` | The port to listen on. Render sets it automatically (its documented default is `10000`); nothing may assume a fixed value (FR-010). |
| `HOST` | entrypoint → `uvicorn --host` | no | `0.0.0.0` | The interface to bind. Set explicitly in `render.yaml` so the value is visible rather than implied. |
| `APP_COMMIT` | `app/core/config.py` | no | *(empty)* | Stamps the commit for a local or CI build. Empty falls through to `RENDER_GIT_COMMIT`. |
| `RENDER_GIT_COMMIT` | `app/core/config.py` | no | *(unset off-Render)* | Set automatically by Render for every deploy; what makes `/healthz` truthful in production (FR-025). |
| `PYTHONUNBUFFERED` | Python | no | `1` (set in the image) | Logs reach Render's stream immediately instead of sitting in a buffer. |

**No variable in this table is secret, and none may become one without the plan being revisited.**
Secrets belong to the pipeline and the platform (FR-027), never to the image.

**Behaviour with nothing supplied** (US4 scenario 3): `docker run -p 8000:8000 <image>` starts and
serves the home page on `http://localhost:8000`, with `/healthz` reporting
`commit: "unknown"` unless the build stamped it.

**Behaviour with a different port** (US4 scenario 2): `docker run -e PORT=9000 -p 9000:9000 <image>`
listens on 9000 with no code change and no rebuild.

## Verification

| Contract row | Verified by |
|---|---|
| Image builds from a clean context | CI `image` job, every pull request and every push to `main` |
| Container serves `/` and `/healthz` | CI `image` job's smoke test, and quickstart V5 locally |
| Honours `PORT` | Quickstart V5 (a second run with `-e PORT=9000`) |
| Starts with no configuration | Quickstart V5 (first run, no `-e` flags) |
| Clean `SIGTERM` shutdown | Quickstart V5 (`docker stop` returns promptly, logs show a graceful shutdown rather than a kill) |
| No secret in the image | `.dockerignore` review in the milestone diff (SC-009) |
