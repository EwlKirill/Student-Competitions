# Student Competitions

A web application for running online knowledge competitions among students. Teachers manage students, a question bank and competitions; students answer questions in writing; answers are scored by an LLM.

> **Status:** milestone 2 in progress — the application is packaged as a Docker image, every pull request is verified by GitHub Actions, and a merge to `main` publishes itself to Render. Implementation is driven by [GitHub Spec Kit](https://github.com/github/spec-kit).

**Public address:** _not published yet._ The Render Blueprint bootstrap generates the hostname; record it here and in the `PUBLIC_BASE_URL` repository variable once it exists (see [`specs/002-public-deploy-cicd/quickstart.md`](specs/002-public-deploy-cicd/quickstart.md), step B1).

## Getting started

### Prerequisites

[`uv`](https://docs.astral.sh/uv/) — and nothing else. **No system Python is required:** `uv` reads `.python-version` and provisions Python 3.13 itself. There is no database to set up, no `.env` file and no API keys.

Docker is needed only to build and run the packaged application ([below](#run-the-packaged-application)); it is not needed for development.

### Setup

```bash
git clone <repository-url>
cd Student-Competitions
uv sync
```

### Run

```bash
uv run uvicorn app.main:app --reload
```

The startup output ends with the address it is serving on:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open <http://127.0.0.1:8000>. If port 8000 is already taken, pass `--port 8001`.

### Test

```bash
uv run pytest
```

### Lint & format

```bash
uv run ruff check .
uv run ruff format --check .
```

## Run the packaged application

The same image the platform runs. Build and start it from a clean checkout with Docker installed, and nothing else:

```bash
docker build --build-arg APP_COMMIT="$(git rev-parse HEAD)" -t student-competitions .
docker run --rm -p 8000:8000 student-competitions
```

Open <http://localhost:8000>. `APP_COMMIT` is optional — it stamps the commit that `/healthz` reports; without it the endpoint reports `"unknown"`.

The port is configuration, not code. To listen somewhere else, with no rebuild:

```bash
docker run --rm -e PORT=9000 -p 9000:9000 student-competitions
```

### Service status

`GET /healthz` reports what is live, as JSON:

```json
{"status": "ok", "version": "0.1.0", "commit": "9f2c1ab3e4d5678901234567890abcdef1234567"}
```

Render uses it as the service's health check, and the deploy pipeline polls it to prove a release actually landed.

### Environment variables

The complete configuration surface. Every one is optional — the application starts on the defaults below with nothing supplied.

| Variable | Read by | Default | Purpose |
|---|---|---|---|
| `PORT` | the container entrypoint (`uvicorn --port`) | `8000` | The port to listen on. Render sets it automatically. |
| `HOST` | the container entrypoint (`uvicorn --host`) | `0.0.0.0` | The interface to bind. Set explicitly in `render.yaml`. |
| `APP_COMMIT` | `app/core/config.py` | *(empty)* | Stamps the commit for a local or CI build. Empty falls through to `RENDER_GIT_COMMIT`. |
| `RENDER_GIT_COMMIT` | `app/core/config.py` | *(unset off-Render)* | Set automatically by Render for every deploy; what makes `/healthz` truthful in production. |
| `PYTHONUNBUFFERED` | Python | `1` (set in the image) | Logs reach the platform's stream immediately instead of sitting in a buffer. |

**None of these is a secret, and no secret may be added to this table.** Secrets belong to the pipeline and the hosting platform, never to the image or the repository.

## Deployment

Hosted on [Render](https://render.com) (free instance type, Frankfurt), configured by [`render.yaml`](render.yaml). Render's own auto-deploy is **off**: the pipeline is the only thing that releases.

### Releasing

Merge to `main`. That is the whole procedure — no commands, no dashboard.

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) then runs the same checks a pull request runs, calls Render's deploy hook pinned to the merged commit, and polls the public `/healthz` until it reports that commit. The workflow only reports success once the public address is actually serving the merged commit; the GitHub **Environments → production** view records which commit went live and when.

### Rolling back

If a release is bad, get the public address healthy first, then fix `main`:

1. **Render dashboard → Deploys → Rollback** on the last successful deploy. Fastest, because nothing is rebuilt, and available to anyone with dashboard access.
2. **Or re-deploy the last good commit** from a terminal:

   ```bash
   export RENDER_DEPLOY_HOOK_URL='<the service deploy hook URL>'
   ./scripts/render_deploy.sh <previous-good-sha>
   ./scripts/wait_for_release.sh https://<public-host> <previous-good-sha>
   ```

Then **revert the bad commit on `main`** and let the pipeline publish the revert, so the repository and the public address agree again. Until that happens, the next merge re-publishes the broken version.

A failed release leaves the previous version serving: Render switches traffic only after a new instance passes its health check.

### Continuous integration

| Workflow | Runs on | Does |
|---|---|---|
| [`checks.yml`](.github/workflows/checks.yml) | called by the two below | `quality` (tests, `ruff check`, `ruff format --check`) and `image` (builds the Dockerfile and smoke-tests the container) |
| [`ci.yml`](.github/workflows/ci.yml) | every pull request against `main` | Calls `checks.yml`. Branch protection requires both jobs, so a failing check blocks the merge. |
| [`deploy.yml`](.github/workflows/deploy.yml) | every push to `main` | Calls `checks.yml`, then deploys and verifies the release. |

Apply the branch protection rule with [`scripts/setup_branch_protection.sh`](scripts/setup_branch_protection.sh) (needs the `gh` CLI, authenticated with admin rights).

## Requirements

- Product requirements: [`docs/requirements/product-requirements.md`](docs/requirements/product-requirements.md)
- Technical requirements & milestones: [`docs/requirements/technical-requirements.md`](docs/requirements/technical-requirements.md)

## Tech stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLite (local) / PostgreSQL (production) via SQLModel + Alembic |
| Authentication | Email OTP + server-side sessions in a signed cookie |
| Answer evaluation | LLM API (Claude or OpenAI) with structured output |
| Containerization | Docker (two-stage build, non-root, uv-locked dependencies) |
| Hosting | Render, configured as code by `render.yaml` |
| CI/CD | GitHub Actions: checks on every pull request, auto-deploy on merge to `main` |
| Tooling | uv, ruff, pytest, Playwright (later) |

## Repository layout

```text
.
├── .claude/skills/          # Spec Kit skills for Claude Code (/speckit-*)
├── .specify/                # Spec Kit: constitution, templates, scripts, workflows
│   └── memory/constitution.md
├── .github/workflows/       # CI/CD
│   ├── checks.yml           # Reusable: quality + image jobs
│   ├── ci.yml               # Pull requests → checks (the merge gate)
│   └── deploy.yml           # Push to main → checks, deploy, verify
├── docs/requirements/       # Source product & technical requirements
├── specs/                   # Feature specs created by /speckit-specify (NNN-feature-name/)
├── Dockerfile               # Two-stage image: uv builder → python:3.13-slim runtime
├── .dockerignore            # Build context: keeps tests, specs, .git and env files out
├── render.yaml              # Render Blueprint: the service, as code
├── pyproject.toml           # Project metadata, dependencies, ruff & pytest config
├── uv.lock                  # Committed lockfile
├── .python-version          # 3.13
├── app/                     # FastAPI application
│   ├── main.py              # App construction: static mount, routers, error handler
│   ├── core/                # Settings, security, sessions, DB engine
│   │   ├── config.py        # APP_NAME, APP_TAGLINE, APP_DESCRIPTION, APP_VERSION, COMMIT_SHA
│   │   └── templates.py     # Shared Jinja2Templates instance
│   ├── models/              # SQLModel tables (milestone 3)
│   ├── schemas/             # Request/response & LLM structured-output schemas
│   ├── routers/             # Route handlers grouped by area/role
│   │   ├── pages.py         # GET / → home page
│   │   └── health.py        # GET /healthz → status, version, commit
│   ├── services/            # Business logic (competitions, scoring, email, LLM)
│   ├── templates/           # Jinja2: layouts/, partials/ (HTMX fragments), pages/
│   │   ├── layouts/base.html
│   │   └── pages/           # home.html, error.html
│   └── static/              # css/ (vendored pico.min.css + app.css), js/, img/
├── migrations/              # Alembic migrations (milestone 3)
├── tests/                   # unit/, integration/, e2e/ (Playwright)
│   ├── conftest.py          # `client` fixture over the FastAPI test client
│   ├── unit/test_config.py
│   └── integration/         # test_home.py, test_health.py
└── scripts/                 # Developer & ops helper scripts
    ├── render_deploy.sh            # Trigger a Render deploy of one commit
    ├── wait_for_release.sh         # Poll /healthz until that commit is serving
    └── setup_branch_protection.sh  # Apply the main branch protection rule
```

The internal layout of `app/` is a starting point; the implementation plan (`/speckit-plan`) may refine it.

## Spec-driven workflow

Requires [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/).

1. `/speckit-constitution` — define project principles (fill `.specify/memory/constitution.md`)
2. `/speckit-specify` — describe a milestone / feature → `specs/NNN-feature/spec.md`
3. `/speckit-clarify` *(optional)* — resolve ambiguities
4. `/speckit-plan` — technical plan for the feature
5. `/speckit-tasks` — break the plan into tasks
6. `/speckit-analyze` *(optional)* — cross-artifact consistency check
7. `/speckit-implement` — implement the tasks

Work one milestone at a time on a feature branch (`NNN-feature-name`) and merge via pull request.

To upgrade Spec Kit files later:

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init --here --force --integration claude --script sh
```
