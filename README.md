# Student Competitions

A web application for running online knowledge competitions among students. Teachers manage students, a question bank and competitions; students answer questions in writing; answers are scored by an LLM..

> **Status:** milestone 3 in progress — the application has a database: sample questions are stored by a migration and listed on the home page, alongside a status line showing the engine, the schema revision and how many times the application has started. Locally it uses a SQLite file; in production, PostgreSQL on Neon. Implementation is driven by [GitHub Spec Kit](https://github.com/github/spec-kit).

**Public address:** <https://student-competitions.onrender.com> — served from Render, HTTPS only. `GET /healthz` there reports the commit currently live.

## Getting started

### Prerequisites

[`uv`](https://docs.astral.sh/uv/) — and nothing else. **No system Python is required:** `uv` reads `.python-version` and provisions Python 3.13 itself. There is no database server to install, no `.env` file and no API keys: locally the application uses a SQLite file that the first migration creates.

Docker is needed only to build and run the packaged application ([below](#run-the-packaged-application)) and, optionally, to run the PostgreSQL half of the test suite ([below](#test)); it is not needed for development.

### Setup

```bash
git clone <repository-url>
cd Student-Competitions
uv sync
```

### Run

```bash
uv run alembic upgrade head          # creates data/student_competitions.sqlite3 at the newest schema
uv run uvicorn app.main:app --reload
```

Run `uv run alembic upgrade head` again after pulling a change that adds a migration. If you forget, the application refuses to start and prints that command. To start over from nothing, stop the application, delete `data/student_competitions.sqlite3` and migrate again.

The startup output ends with the address it is serving on:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open <http://127.0.0.1:8000>. If port 8000 is already taken, pass `--port 8001`.

### Test

```bash
uv run pytest
```

Every test that touches the database runs twice, as `[sqlite]` and `[postgresql]`. Without further setup the SQLite cases run and the PostgreSQL ones are skipped with a reason. To run both engines the way CI does, start a password-less PostgreSQL 17 and point `TEST_POSTGRES_URL` at it:

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest
docker rm -f sc-pg                   # when done
```

The suite creates and drops its own uniquely named databases on that server, and never touches `data/` or whatever `DATABASE_URL` points to. In CI (`CI=true`) a missing `TEST_POSTGRES_URL` fails the run at start, so the PostgreSQL half can never be skipped silently.

### Adding a migration

Every change to the database structure is an Alembic migration in `migrations/versions/`; nothing creates tables any other way.

```bash
# 1. change or add a model in app/models/ (and import it in app/models/__init__.py)
uv run alembic revision --autogenerate -m "short description"
# 2. read the generated file and fix what autogenerate got wrong
uv run alembic upgrade head
uv run pytest                        # the drift, single-head and stairway tests guard the history
```

Rules that keep releases safe:

- **Keep the previous release working.** During a deploy the old and the new version run side by side for a moment, both against the new schema. Add first (a new column, a new table) and remove in a later release, never both in one.
- **Data migrations use a frozen table.** Describe the table with `sa.table(...)` inside the migration; never import from `app`, whose models will change later.
- **Migrations run themselves on release.** The container runs `alembic upgrade head` before starting the application; there is no manual production command. On PostgreSQL the whole upgrade is one transaction behind an advisory lock, so a failure changes nothing and two starting instances cannot both apply it.
- **SQLite is not transactional for schema changes.** A failed local migration may leave `data/student_competitions.sqlite3` half-migrated: fix the migration and run it again, or delete the file and migrate from scratch.

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

The container migrates its database before the application starts. With no `DATABASE_URL` it uses a throw-away SQLite file inside the container; to use a PostgreSQL database instead, pass `-e DATABASE_URL=postgresql://…`.

The port is configuration, not code. To listen somewhere else, with no rebuild:

```bash
docker run --rm -e PORT=9000 -p 9000:9000 student-competitions
```

On macOS, if the build fails with `docker-credential-desktop: executable file not found in $PATH`,
Docker Desktop's credential helper is not on your `PATH`. Add it:

```bash
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
```

### Service status

`GET /healthz` reports what is live, as JSON:

```json
{"status": "ok", "version": "0.1.0", "commit": "9f2c1ab3e4d5678901234567890abcdef1234567"}
```

Render uses it as the service's health check, and the deploy pipeline polls it to prove a release actually landed.

Every page also carries the same release identity in its footer — `v<version>` and the short commit, with the full SHA on hover — so which release is serving is visible without leaving the page.

### Environment variables

The complete configuration surface. Locally every one is optional — the application starts on the defaults below with nothing supplied. On Render, `DATABASE_URL` is required.

| Variable | Read by | Default | Purpose |
|---|---|---|---|
| `PORT` | the container entrypoint (`uvicorn --port`) | `8000` | The port to listen on. Render sets it automatically. |
| `HOST` | the container entrypoint (`uvicorn --host`) | `0.0.0.0` | The interface to bind. Set explicitly in `render.yaml`. |
| `APP_COMMIT` | `app/core/config.py` | *(empty)* | Stamps the commit for a local or CI build. Empty falls through to `RENDER_GIT_COMMIT`. |
| `RENDER_GIT_COMMIT` | `app/core/config.py` | *(unset off-Render)* | Set automatically by Render for every deploy; what makes `/healthz` truthful in production. |
| `PYTHONUNBUFFERED` | Python | `1` (set in the image) | Logs reach the platform's stream immediately instead of sitting in a buffer. |
| `DATABASE_URL` | `app/core/config.py` and `migrations/env.py` | `sqlite:///<repository>/data/student_competitions.sqlite3`, **only when not on Render** | Where the database is. `sqlite:///…` or `postgresql://…` (also `postgres://`; normalised to the psycopg driver). **A secret in production**: Neon's connection string, set only in Render's dashboard and never committed, pasted or logged. |
| `RENDER` | `app/core/config.py` | *(unset)* | Set to `true` by Render. Turns a missing `DATABASE_URL` into a refusal to start instead of a silent fallback to SQLite. Do not set it locally. |
| `TEST_POSTGRES_URL` | `tests/conftest.py` only | *(unset: PostgreSQL tests skipped)* | **Tests only** — never read by the application. A PostgreSQL server where the tests may create databases. Not a secret (a disposable, password-less server). |

`DATABASE_URL` in production is the **only** secret the application reads. It lives in Render's service environment and nowhere else: not in this repository, not in the image and not in GitHub. Everything else in this table is not secret.

## Deployment

Hosted on [Render](https://render.com) (free instance type, Frankfurt), configured by [`render.yaml`](render.yaml). Render's own auto-deploy is **off**: the pipeline is the only thing that releases.

### Releasing

Merge to `main`. That is the whole procedure — no commands, no dashboard.

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) then runs the same checks a pull request runs, calls Render's deploy hook pinned to the merged commit, and polls the public `/healthz` until it reports that commit. The workflow only reports success once the public address is actually serving the merged commit; the GitHub **Environments → production** view records which commit went live and when.

Each release runs `alembic upgrade head` before the new version serves: the container's entrypoint migrates, then starts the application. A failed migration stops the container before it opens its port, so Render keeps the previous release serving. After the release, the deploy job checks the home page's status line with [`scripts/database_status.sh`](scripts/database_status.sh): it must show this commit's schema revision and a boot count higher than before the release, which proves the data survived the redeploy.

### Production database

PostgreSQL 17 on Neon's free plan (project `student-competitions`, AWS Europe Central 1 / Frankfurt), next to the Render service. Render reads its **direct** (non-pooled) connection string from the `DATABASE_URL` environment variable, declared in `render.yaml` without a value and entered once in the dashboard. The one-time bootstrap is described in [`specs/003-database-questions/quickstart.md`](specs/003-database-questions/quickstart.md#one-time-bootstrap-production-database).

To rotate the credential: in Neon, reset the role's password and copy the new connection string; in Render → service → Environment, replace `DATABASE_URL` and choose **Save, rebuild, and deploy**.

### Rolling back

If a release is bad, get the public address healthy first, then fix `main`:

1. **Render dashboard → Deploys → Rollback** on the last successful deploy. Fastest, because nothing is rebuilt, and available to anyone with dashboard access.
2. **Or re-deploy the last good commit** from a terminal:

   ```bash
   export RENDER_DEPLOY_HOOK_URL='<the service deploy hook URL>'
   ./scripts/render_deploy.sh <previous-good-sha>
   ./scripts/wait_for_release.sh https://student-competitions.onrender.com <previous-good-sha>
   ```

Then **revert the bad commit on `main`** and let the pipeline publish the revert, so the repository and the public address agree again. Until that happens, the next merge re-publishes the broken version.

A failed release leaves the previous version serving: Render switches traffic only after a new instance passes its health check.

### Continuous integration

| Workflow | Runs on | Does |
|---|---|---|
| [`checks.yml`](.github/workflows/checks.yml) | called by the two below | `quality` (tests on SQLite and on a PostgreSQL service, `ruff check`, `ruff format --check`) and `image` (builds the Dockerfile, checks it refuses to start on Render without a database, and smoke-tests the container against PostgreSQL across a restart) |
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
| Database | SQLModel + Alembic migrations, psycopg 3; SQLite locally and in tests, PostgreSQL 17 on Neon's free plan in production (and in CI) |
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
├── Dockerfile               # Two-stage image: uv builder → python:3.13-slim runtime; migrates, then serves
├── .dockerignore            # Build context: keeps tests, specs, .git, env files and local databases out
├── render.yaml              # Render Blueprint: the service, as code
├── alembic.ini              # Alembic: script location, file naming, ruff hooks (no database URL)
├── pyproject.toml           # Project metadata, dependencies, ruff & pytest config
├── uv.lock                  # Committed lockfile
├── .python-version          # 3.13
├── app/                     # FastAPI application
│   ├── main.py              # App construction: startup (database guard, boot count), routers, error handler
│   ├── core/                # Settings, security, sessions, DB engine
│   │   ├── config.py        # App constants, COMMIT_SHA, resolve_database_url
│   │   ├── db.py            # Engine, per-request session, UTC timestamp column type
│   │   ├── migrations.py    # Expected (head) and current schema revision; startup guard
│   │   └── templates.py     # Shared Jinja2Templates instance
│   ├── models/              # SQLModel tables: Question, BootCounter
│   ├── schemas/             # Validation and view schemas: QuestionCreate/Update/Public
│   ├── routers/             # Route handlers grouped by area/role
│   │   ├── pages.py         # GET / → home page with the question list and status line
│   │   └── health.py        # GET /healthz → status, version, commit
│   ├── services/            # Business logic: questions (CRUD), database_status (boot count)
│   ├── templates/           # Jinja2: layouts/, partials/ (HTMX fragments), pages/
│   │   ├── layouts/base.html
│   │   └── pages/           # home.html, error.html
│   └── static/              # css/ (vendored pico.min.css + app.css), js/, img/
├── migrations/              # Alembic migrations
│   ├── env.py               # Uses resolve_database_url; one locked transaction on PostgreSQL
│   └── versions/            # Revisions: tables + boot counter, then the sample questions
├── data/                    # Local SQLite database (git-ignored, created by the first migration)
├── tests/                   # unit/, integration/, e2e/ (Playwright)
│   ├── conftest.py          # Both-engine database fixtures (template + clone), `client`
│   ├── unit/                # test_config.py, test_database_config.py, test_question_schemas.py
│   └── integration/         # home, health, routes, startup, migrations, boot counter, question service
└── scripts/                 # Developer & ops helper scripts
    ├── render_deploy.sh            # Trigger a Render deploy of one commit
    ├── wait_for_release.sh         # Poll /healthz until that commit is serving
    ├── database_status.sh          # Read the public boot count; verify revision and boot count after a release
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
