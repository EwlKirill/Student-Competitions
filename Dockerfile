# The packaged application: one self-contained, reproducible unit that a developer, the CI
# `image` job and Render all run identically (FR-008, FR-011).
# Contract: specs/002-public-deploy-cicd/contracts/container.md — rationale: research D5.

# ---------------------------------------------------------------------------------------------
# Builder — resolves the locked dependencies into a virtualenv, and ships none of its own tooling
# ---------------------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Bytecode compiled ahead of time (faster cold starts), copied rather than hardlinked across the
# layer boundary, and no interpreter downloads — the base image already has Python 3.13.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Only the dependency manifests, so this layer is re-used on every build that does not change
# them. `--locked` fails the build if `uv.lock` is out of step with `pyproject.toml` (FR-018),
# `--no-dev` leaves the test and lint tooling out of the image, and `--no-install-project` keeps
# the application itself out of the virtualenv — it is copied in as source below.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# ---------------------------------------------------------------------------------------------
# Runtime — the same Python minor version and Debian release, so the copied virtualenv is valid
# ---------------------------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

# Stamps the commit for a local or CI build. Empty by default, which `app/core/config.py` treats
# as "not set" so Render's automatic RENDER_GIT_COMMIT still wins on a deployed instance.
ARG APP_COMMIT=""
ENV APP_COMMIT=$APP_COMMIT

# Logs reach the platform's stream immediately instead of sitting in a buffer.
ENV PYTHONUNBUFFERED=1

# The virtualenv's interpreter first, so `uvicorn` and `python` resolve to it without activation.
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Root-owned and world-readable: the application runs as a user that cannot modify its own
# dependencies or source.
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

# Non-root, with no login shell and no home directory to write to. The uid is well above the
# range Debian reserves for system accounts, so it cannot collide with one the base image adds
# later; `--system` is deliberately absent, since it warns about exactly that uid range.
RUN useradd --no-create-home --shell /usr/sbin/nologin --uid 10001 appuser
USER appuser

# Documentation only — the real port comes from $PORT.
EXPOSE 8000

# There is no curl in this image, so the check is a Python one-liner. Render uses
# `healthCheckPath` from render.yaml instead; this makes `docker run` behave like production and
# gives the CI smoke test something to wait on.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"

# `sh -c` because the exec form does not expand ${PORT}; `exec` so uvicorn becomes PID 1 and
# receives SIGTERM directly — without it the shell stays PID 1, does not forward the signal, and
# every redeploy ends in a SIGKILL after the platform's grace period instead of a clean shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
