# Student Competitions

A web application for running online knowledge competitions among students. Teachers manage students, a question bank and competitions; students answer questions in writing; answers are scored by an LLM.

> **Status:** milestone 1 complete — the application runs locally and serves a server-rendered home page covered by a pytest test. Implementation is driven by [GitHub Spec Kit](https://github.com/github/spec-kit).

## Getting started

### Prerequisites

[`uv`](https://docs.astral.sh/uv/) — and nothing else. **No system Python is required:** `uv` reads `.python-version` and provisions Python 3.13 itself. There is no database to set up, no `.env` file and no API keys.

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
| Deployment | Docker + Render (or Railway / Fly.io) |
| Tooling | uv, ruff, pytest, Playwright (later) |

## Repository layout

```text
.
├── .claude/skills/          # Spec Kit skills for Claude Code (/speckit-*)
├── .specify/                # Spec Kit: constitution, templates, scripts, workflows
│   └── memory/constitution.md
├── .github/
│   ├── workflows/           # CI/CD (milestone 2)
│   └── pull_request_template.md
├── docs/requirements/       # Source product & technical requirements
├── specs/                   # Feature specs created by /speckit-specify (NNN-feature-name/)
├── pyproject.toml           # Project metadata, dependencies, ruff & pytest config
├── uv.lock                  # Committed lockfile
├── .python-version          # 3.13
├── app/                     # FastAPI application
│   ├── main.py              # App construction: static mount, routers, error handler
│   ├── core/                # Settings, security, sessions, DB engine
│   │   ├── config.py        # APP_NAME, APP_TAGLINE, APP_DESCRIPTION
│   │   └── templates.py     # Shared Jinja2Templates instance
│   ├── models/              # SQLModel tables (milestone 3)
│   ├── schemas/             # Request/response & LLM structured-output schemas
│   ├── routers/             # Route handlers grouped by area/role
│   │   └── pages.py         # GET / → home page
│   ├── services/            # Business logic (competitions, scoring, email, LLM)
│   ├── templates/           # Jinja2: layouts/, partials/ (HTMX fragments), pages/
│   │   ├── layouts/base.html
│   │   └── pages/           # home.html, error.html
│   └── static/              # css/ (vendored pico.min.css + app.css), js/, img/
├── migrations/              # Alembic migrations (milestone 3)
├── tests/                   # unit/, integration/, e2e/ (Playwright)
│   ├── conftest.py          # `client` fixture over the FastAPI test client
│   └── integration/test_home.py
└── scripts/                 # Developer & ops helper scripts
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
