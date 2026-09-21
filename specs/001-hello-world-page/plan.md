# Implementation Plan: Hello World Page (Milestone 1)

**Branch**: `001-hello-world-page` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-hello-world-page/spec.md`

## Summary

Turn the empty repository skeleton into a runnable, testable FastAPI application that
server-renders one home page. A single route (`GET /`) renders a Jinja2 template that extends a
shared base layout, styled by a locally vendored copy of Pico.css served from `/static`. Unknown
paths render a friendly "not found" page instead of a JSON error or a stack trace. Dependencies
and the Python version are managed by `uv` (`pyproject.toml` + committed `uv.lock`), and a pytest
integration test drives the app through the FastAPI test client to assert the root returns `200`
with the application name in the HTML.

No database, no configuration from the environment, no authentication, no HTMX — this milestone
only proves the end-to-end request path and establishes the test harness every later milestone
builds on.

## Technical Context

**Language/Version**: Python 3.13 (pinned via `.python-version` and `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**: FastAPI (routing/ASGI app), Uvicorn (ASGI server), Jinja2 (server-side
templates), Pico.css 2.x (vendored stylesheet, no build step). Dev-only: pytest, httpx (required
by the Starlette/FastAPI test client), ruff.

**Storage**: N/A — no database, no files written at runtime. SQLModel/Alembic arrive in milestone 3.

**Testing**: pytest with `fastapi.testclient.TestClient`; tests under `tests/integration/`.
`tests/unit/` and `tests/e2e/` stay empty at this milestone.

**Target Platform**: Local developer machine (macOS/Linux), run with `uv run uvicorn`. Containers
and hosting arrive in milestone 2.

**Project Type**: Single server-rendered web application (one FastAPI app, one deployment unit).

**Performance Goals**: Home page rendered and delivered in well under 2 s on a local run (SC-003);
full test suite under 30 s (SC-004). Both are trivially met by a static server-rendered page —
no tuning work is planned.

**Constraints**: The application MUST start and serve the home page with no network access, no
environment variables, no credentials and no database (FR-010). This forbids CDN-hosted CSS and
any startup call to an external service. The page MUST remain readable if the stylesheet fails to
load, which means semantic HTML carries the structure and CSS is purely presentational.

**Scale/Scope**: One route plus a static mount and a 404 handler; two templates; one test module.
Expected footprint under ~150 lines of application code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Verdict | Evidence / Notes |
|---|---|---|---|
| I | Walking Skeleton & Vertical Slices | **PASS** | This is milestone 1 of the ladder in `docs/requirements/technical-requirements.md`, delivered as feature `specs/001-hello-world-page/` on branch `001-hello-world-page`. It is a full vertical slice (request → route → template → styled HTML → test), not a horizontal layer. Nothing from milestones 2+ (Docker, CI, DB, auth) is built here. |
| II | Server-Rendered Simplicity | **PASS** | The page is rendered on the server by Jinja2 and returned as complete HTML; no client-side rendering, no custom JavaScript, no build step. Styling is Pico.css plus a small override file in `app/static/css/`. HTMX is listed as "milestone 1+ (as needed)" and is **not** needed: the page is static content with no partial updates, so adding it now would violate YAGNI. It enters with the first interactive feature. |
| III | Test-Backed Delivery | **PASS with recorded deviation** | The milestone's `_Test:_` criterion ("there is a first pytest test for the endpoint") is automated in `tests/integration/test_home.py`: root returns `200`, response is HTML containing the application name, the page has a `<title>`, the `<head>` carries the viewport meta, and an unknown path returns `404`. That covers US1 scenarios 1–2 and the machine-checkable half of scenario 3, plus US3 scenario 2. The remaining acceptance scenarios — visual reflow at phone width, clean-checkout setup, startup address reporting, the deliberate-breakage check — are verified manually per quickstart.md; see **Complexity Tracking** below for why and for the deviation record Principle III's "the spec's acceptance scenarios" wording requires. CI enforcement starts in milestone 2 per the stack table, so lint/tests are run locally here (see the same table). |
| IV | Role-Based Access & Data Scoping | **N/A (justified)** | No roles, users, sessions or personal data exist at this milestone (auth is milestone 4, roles milestone 5). The home page is deliberately public — it is an anonymous marketing/landing page, which is the intended access level, not a missing check. The deny-by-default rule binds from the moment authentication exists; the reusable role dependencies are introduced in milestone 5 and every route added from then on carries an explicit requirement. |
| V | Secure Authentication & Secrets | **N/A / PASS** | No authentication, sessions, cookies or secrets are introduced. Nothing in the diff reads or stores credentials, and no `.env` file is created or required — the app starts with zero configuration (FR-010). |
| VI | Trustworthy LLM Evaluation | **N/A** | No LLM usage (milestone 10). |
| VII | Data Integrity & Migrations | **N/A** | No database, no models, no `create_all()`, no timestamps. `migrations/` stays empty until milestone 3. |
| — | Technology Stack table | **PASS** | Only milestone-1 components are introduced: Python + FastAPI, Jinja2, Pico.css, uv, ruff, pytest. No milestone-2+ component (Docker, GitHub Actions, SQLModel, Alembic, Playwright) is added early. |
| — | Application Layout | **PASS** | Uses the mandated `app/` layout: `core/` (constants), `routers/` (thin handler), `templates/layouts|pages/`, `static/css/`. `models/`, `schemas/`, `services/` and `templates/partials/` stay empty — this milestone has no business logic to put in a service, and inventing one would be an abstraction without a present need (Principle II, YAGNI). |
| — | Open stack decision: Python version | **RESOLVED** | Python **3.13**, pinned in `.python-version` and `requires-python`. Rationale and alternatives in [research.md](./research.md#d1-python-version). |

**New runtime dependencies** (Principle II requires justification in this plan):

| Dependency | Scope | Justification |
|---|---|---|
| `fastapi` | runtime | The stack's web framework (constitution, milestone 1). |
| `uvicorn[standard]` | runtime | FastAPI ships no server of its own; an ASGI server is required to satisfy FR-007. Uvicorn is FastAPI's documented default and is part of the "Python + FastAPI" stack row, not a new stack category. |
| `jinja2` | runtime | The stack's templating engine (constitution, milestone 1). |
| `pytest` | dev | The stack's test runner (constitution, milestone 1). |
| `httpx` | dev | Hard requirement of `fastapi.testclient.TestClient`; test-only, never imported by `app/`. |
| `ruff` | dev | The stack's linter/formatter (constitution, milestone 1). |
| Pico.css 2.x | vendored asset | The stack's styling choice. Committed as a static file rather than installed, so there is no CSS build step and no network dependency (FR-010). |

**Post-Phase 1 re-check**: PASS — no gate changed after the design artifacts were produced. The
design added no dependency, no abstraction, no configuration surface and no route beyond the two
documented in [contracts/http-routes.md](./contracts/http-routes.md).

## Project Structure

### Documentation (this feature)

```text
specs/001-hello-world-page/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification (/speckit-specify)
├── research.md          # Phase 0 output — decisions & alternatives
├── data-model.md        # Phase 1 output — view model only (no persistence)
├── quickstart.md        # Phase 1 output — run & validation guide
├── contracts/
│   └── http-routes.md   # Phase 1 output — HTTP surface contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
.python-version                     # 3.13
pyproject.toml                      # project metadata, deps, ruff & pytest config
uv.lock                             # committed lockfile
README.md                           # + Getting started section (setup / run / test)

app/
├── __init__.py
├── main.py                         # FastAPI app: static mount, router include, 404 handler
├── core/
│   ├── __init__.py
│   ├── config.py                   # APP_NAME, APP_DESCRIPTION, APP_TAGLINE constants
│   └── templates.py                # shared Jinja2Templates instance (imported by routers + main)
├── routers/
│   ├── __init__.py
│   └── pages.py                    # GET / → renders pages/home.html
├── templates/
│   ├── layouts/
│   │   └── base.html               # <html>, <head>, Pico.css + overrides, {% block %}s
│   ├── pages/
│   │   ├── home.html               # extends base; app name + description
│   │   └── error.html              # extends base; friendly "not found" page
│   └── partials/                   # (empty — HTMX fragments arrive with the first interaction)
├── static/
│   └── css/
│       ├── pico.min.css            # vendored Pico.css 2.x
│       └── app.css                 # project overrides (kept minimal)
├── models/                         # (empty — milestone 3)
├── schemas/                        # (empty — milestone 3)
└── services/                       # (empty — no business logic yet)

tests/
├── __init__.py
├── conftest.py                     # `client` fixture over fastapi.testclient.TestClient
├── integration/
│   ├── __init__.py
│   └── test_home.py                # root 200 + app name + title; unknown path 404
├── unit/                           # (empty)
└── e2e/                            # (empty — Playwright, milestone 12)
```

**Structure Decision**: Single-project layout, exactly as fixed by the constitution's
*Application Layout* section — one FastAPI application under `app/` serving all pages, with tests
mirrored under `tests/`. No refinement of the mandated layout is needed at this milestone; the
directories that have no content yet keep their `.gitkeep` files so the shape stays visible.
`app/main.py` holds app construction (static mount, router registration, error handler) and
`app/routers/pages.py` holds the thin handler, keeping the router free of application wiring.

The one shared object both of them need — the `Jinja2Templates` instance — lives in
`app/core/templates.py` rather than in `app/main.py`. `main.py` imports the router, so a router
importing `templates` back from `app.main` would close an import cycle and fail at startup;
`core/` is where the constitution's *Application Layout* already puts shared wiring, and every
later milestone's router inherits the same single instance without reaching into `main`.

## Complexity Tracking

No added complexity and no stack deviation. Two process deviations from the constitution are
recorded here, as Governance requires — each with the simpler alternative and why it was rejected.

| Deviation | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| **Principle III**: four acceptance scenarios are verified manually (quickstart V2, V3, V5, V6, V7 step 3 → tasks T024, T025, T030, T032, T033), not by pytest. Automated coverage is US1 scenarios 1–2 and the viewport half of scenario 3, plus US3 scenarios 1–2. | The manual four are about the *browser rendering* (text reflow at 375 px, readability with CSS blocked) and the *developer's environment* (clone-to-page on a clean checkout, a second process failing on a bound port). Asserting them needs a real browser — Playwright — which the stack table places in milestone 12, and a subprocess-level test of `uv sync` + `uvicorn`, which is milestone 2's CI job. | Adding Playwright now would introduce a milestone-12 stack component eight milestones early, in direct conflict with Principle I and the stack table's "a component MUST be introduced in the milestone listed above, or later". A test asserting the README's contents (for US2 scenario 3) fits none of the constitution's three tiers — it is neither pure logic, an HTTP route, nor e2e — and would assert the shape of prose rather than behaviour. The deliberate-breakage check (SC-005) is inherently a once-before-acceptance procedure: a test that asserts the suite fails when the app is broken would have to break the app. |
| **Development Workflow gate 3** ("CI is green: `ruff check`, `ruff format --check`, full pytest suite") cannot be satisfied by this milestone's pull request. | No CI exists yet: GitHub Actions is a milestone-2 component in the stack table, and `.github/` is not created by this feature. The gate binds from milestone 2 onward. | Standing up GitHub Actions now would pull milestone 2's work into milestone 1, which Principle I forbids ("work beyond the current milestone's scope MUST be deferred"). Instead T031 runs the three gate commands locally before the PR, on the same configuration milestone 2's workflow will invoke, so that pipeline starts life on an already-green tree. |
