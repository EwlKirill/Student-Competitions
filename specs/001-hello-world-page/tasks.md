---

description: "Task list for Hello World Page (Milestone 1)"
---

# Tasks: Hello World Page (Milestone 1)

**Input**: Design documents from `/specs/001-hello-world-page/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included. The spec requests them explicitly — User Story 3 is entirely about the automated test suite, and FR-008 requires it. Because the tests are their own priority-P3 story, they live in Phase 5 rather than being folded into User Story 1.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and demoed independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project, layout fixed by the constitution's *Application Layout*: `app/` for the FastAPI application, `tests/` for the suite, both at repository root. Paths below are relative to the repository root (`/Users/serhiionofreichuk/progr/student_competitions/Student-Competitions`).

The repository already contains the empty directory skeleton (`app/core/`, `app/routers/`, `app/templates/{layouts,pages,partials}/`, `app/static/{css,js,img}/`, `app/models/`, `app/schemas/`, `app/services/`, `tests/{unit,integration,e2e}/`), each holding a `.gitkeep`. Tasks below fill it in; they do not recreate it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Turn the empty skeleton into a `uv`-managed Python project with pinned dependencies and configured tooling.

- [ ] T001 Create `.python-version` at repository root containing exactly `3.13` (research.md D1 — `uv` provisions the interpreter, so no system Python is required)
- [ ] T002 Create `pyproject.toml` at repository root with `[project]` metadata (name `student-competitions`, version `0.1.0`, description), `requires-python = ">=3.13,<3.14"` verbatim per research.md D1, and runtime `dependencies = ["fastapi", "uvicorn[standard]", "jinja2"]` — do NOT use `fastapi[standard]` (research.md D2 rejects it for pulling unjustified extras)
- [ ] T003 Add a dev dependency group to `pyproject.toml` with `pytest`, `httpx` (hard requirement of `fastapi.testclient.TestClient`, never imported by `app/`) and `ruff`
- [ ] T004 Add `[tool.ruff]` config to `pyproject.toml`: `target-version = "py313"`, `line-length = 100`, and `[tool.ruff.lint]` `select = ["E", "F", "I", "UP", "B"]` (research.md D8, values verbatim)
- [ ] T005 Add `[tool.pytest.ini_options]` to `pyproject.toml` with `testpaths = ["tests"]` so `uv run pytest` is the single documented test command (FR-008)
- [ ] T006 Run `uv sync` from repository root and commit the generated `uv.lock` alongside `pyproject.toml` (quickstart.md acceptance checklist requires the lockfile be committed)
- [ ] T007 [P] Create `.gitignore` at repository root ignoring `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.DS_Store`

**Checkpoint**: `uv sync` completes offline-capable and `uv run python -c "import fastapi"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The application package, its single source of truth for user-facing strings, the vendored stylesheet and the shared base layout. Every user story below depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T008 Create `app/__init__.py` (empty) to make `app` an importable package — required by the `app.main:app` import path that milestone 2's Dockerfile will reuse unchanged
- [ ] T009 [P] Create empty `app/core/__init__.py` and `app/routers/__init__.py`
- [ ] T010 [P] Create `app/core/config.py` defining exactly three module-level string constants per data-model.md: `APP_NAME` (short product name, e.g. `"Student Competitions"`), `APP_TAGLINE` (one short line under the name), `APP_DESCRIPTION` (one or two sentences stating what the application is for). Constraints quoted from data-model.md: "All three MUST be non-empty"; "`APP_DESCRIPTION` MUST read as plain prose to someone who has never seen the project (SC-006)"; "Values are literals, not read from the environment" — no `pydantic-settings`, no `.env`, no `os.environ` (FR-010, research.md D6)
- [ ] T011 [P] Vendor Pico.css 2.x **full build** (`pico.min.css`, minified) as `app/static/css/pico.min.css` — committed to the repository, never linked from a CDN (research.md D3, FR-010). It must be the full build, not `pico.classless.min.css`: the classless build has no `.container` class, and T013's layout uses `class="container"`
- [ ] T012 [P] Create `app/static/css/app.css` holding only project-specific overrides, "kept minimal" per plan.md — at this milestone just the few cosmetic touches the home page hero needs (research.md D4). Do not hand-write responsive media queries; Pico's container and type scale satisfy FR-005
- [ ] T013 Create `app/templates/layouts/base.html`: full `<html>` document with `<meta charset>`, `<meta name="viewport" content="width=device-width, initial-scale=1">` verbatim (FR-005, contract requirement), `<meta name="description">` fed by `app_description`, a `<title>` block containing `app_name` (FR-004), and `<link>` tags to `/static/css/pico.min.css` **then** `/static/css/app.css` in that order (contracts/http-routes.md). Use semantic `<header>`/`<main class="container">` wrappers and Jinja `{% block %}`s for title and content, so the page degrades to readable structured text if the stylesheets fail to load (research.md D3 follow-on)
- [ ] T014 Create `app/main.py` constructing the FastAPI application: `app = FastAPI(...)`, mount `StaticFiles(directory="app/static")` at `/static` (no directory listing, nothing outside `app/static` reachable — contracts/http-routes.md), and create the module-level `Jinja2Templates(directory="app/templates")` instance that routers and the error handler share. No database engine import, no environment reads, no startup call to any external service (FR-010)

**Checkpoint**: `uv run uvicorn app.main:app` starts and `curl -I http://127.0.0.1:8000/static/css/pico.min.css` returns `200 text/css`. Foundation ready — user stories can now begin.

---

## Phase 3: User Story 1 - Visitor opens the application home page (Priority: P1) 🎯 MVP

**Goal**: A browser request to the root address returns a complete, styled, server-rendered HTML page carrying the application name and a description of its purpose — and any unknown path returns a friendly "not found" page instead of raw JSON or a stack trace.

**Independent Test**: Start the application, open its address in a browser, and confirm the home page loads with the application name and description visible, a descriptive browser-tab title, and a readable layout. Then open `/about` and confirm a styled 404 page appears.

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create `app/templates/pages/home.html` extending `layouts/base.html`: an `<h1>` containing `app_name` (FR-002), the tagline, and a `<p>` carrying `app_description` — one or two sentences stating the application's purpose (FR-002, SC-006). Complete server-rendered markup only, no client-side rendering and no custom JavaScript (FR-003, Principle II)
- [ ] T016 [P] [US1] Create `app/templates/pages/error.html` extending `layouts/base.html`: shows `status_code`, a short human-readable message from `detail`, and a link back to `/`. Forbidden content per contracts/http-routes.md: "No stack trace, no framework debug output, no internal path"
- [ ] T017 [US1] Create `app/routers/pages.py` with an `APIRouter` and a thin `GET /` handler returning `templates.TemplateResponse("pages/home.html", ...)` with the context `{"app_name": APP_NAME, "app_tagline": APP_TAGLINE, "app_description": APP_DESCRIPTION}` verbatim from data-model.md, plus the `request` that Starlette's template response requires. Import the constants from `app.core.config` — never duplicate the literals (research.md D6: a duplicated literal makes the test pass even when the page is wrong). Keep application wiring out of this module (depends on T010, T015)
- [ ] T018 [US1] Register the pages router on the app in `app/main.py` via `app.include_router(...)` so `GET /` resolves (depends on T014, T017)
- [ ] T019 [US1] Register a Starlette `HTTPException` handler in `app/main.py` that renders `pages/error.html` with context `{"app_name": APP_NAME, "status_code": <int>, "detail": <str>}` verbatim from data-model.md and returns the original exception's status code unchanged. Register it for `HTTPException` generally, not only `404`, so later milestones inherit the friendly page (research.md D5, FR-006). Do NOT add a catch-all `/{path:path}` route — research.md D5 rejects it as it would shadow real routes (depends on T014, T016)
- [ ] T020 [US1] Run quickstart.md **V1** manually: start the app, open <http://127.0.0.1:8000>, then `curl -s http://127.0.0.1:8000 | head -40` and confirm complete HTML with the name and description arrives from the server, not an empty shell (FR-001…FR-004, SC-002, SC-003)
- [ ] T021 [US1] Run quickstart.md **V4** manually: `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:8000/about` returns `404 text/html; charset=utf-8`, and the same path in a browser shows the styled "not found" page with a link home (FR-006)

**Checkpoint**: User Story 1 is fully functional and demoable on its own — the MVP for this milestone.

---

## Phase 4: User Story 2 - Developer runs the application locally (Priority: P2)

**Goal**: A developer with a clean checkout can install dependencies and start the application using short documented commands, and reach the home page at the reported local address.

**Independent Test**: On a clean checkout, follow only the written setup steps in the README and confirm the application starts, reports its local address, and serves the home page there.

### Implementation for User Story 2

- [ ] T022 [US2] Add a "Getting started" section to `README.md` documenting, per quickstart.md and FR-009: prerequisites (`uv` only — "no system Python is required"), setup (`git clone …`, `cd Student-Competitions`, `uv sync`), run (`uv run uvicorn app.main:app --reload`, serving <http://127.0.0.1:8000>), test (`uv run pytest`), and lint/format (`uv run ruff check .`, `uv run ruff format --check .`). Also update the README's "Status" line, which currently reads "no features are implemented yet"
- [ ] T023 [US2] Update the "Repository layout" tree in `README.md` to show the now-populated `app/` and `tests/` structure
- [ ] T024 [US2] Run quickstart.md **V5** manually: clone into a fresh directory and follow README **Setup** → **Run** using only the documented commands; confirm clone-to-visible-page in under 10 minutes (SC-001) and that the startup output names the address it is listening on (FR-007, US2 scenarios 1–3)
- [ ] T025 [US2] Run quickstart.md **V6** manually: with the app running, start a second instance with the same command and confirm it exits with a clear `[Errno 48] Address already in use` (errno 98 on Linux) rather than hanging or failing silently, and that `--port 8001` works. No code change is expected — Uvicorn provides this (research.md D2)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Automated test proves the page works (Priority: P3)

**Goal**: A single command runs a pytest suite that verifies the home page responds successfully with the expected content, so regressions are caught without manual checking.

**Independent Test**: Run `uv run pytest` on a clean checkout and confirm the suite passes and includes at least one test covering the home page.

### Tests for User Story 3

> These tasks ARE the story — the deliverable is the suite itself. Write T028 before running it; T030 proves it fails when the page is broken.

- [ ] T026 [P] [US3] Create empty `tests/__init__.py` and `tests/integration/__init__.py`. Leave `tests/unit/` and `tests/e2e/` empty with their `.gitkeep` files — research.md D7: there is no pure logic to unit-test yet, and Playwright arrives in milestone 12
- [ ] T027 [US3] Create `tests/conftest.py` exposing a session-scoped `client` fixture wrapping `fastapi.testclient.TestClient(app)` over the real `app.main:app` — no live server and no bound port, keeping the suite fast and free of port-in-use flakiness (research.md D7)
- [ ] T028 [US3] Create `tests/integration/test_home.py` asserting, per research.md D7 and contracts/http-routes.md: (a) `GET /` returns `200`; (b) `Content-Type` is `text/html; charset=utf-8`; (c) the body contains `APP_NAME` **imported from `app.core.config`**, not a hard-coded literal; (d) `APP_NAME` is truthy — data-model.md requires this so the containment assertion is not vacuous; (e) the response has a non-empty `<title>`; (f) `GET /about` returns `404` and renders HTML (depends on T017, T019, T027)
- [ ] T029 [US3] Run `uv run pytest` and confirm the suite passes with zero failures in well under 30 seconds (SC-004, US3 scenario 1)
- [ ] T030 [US3] Run quickstart.md **V7** step 3 — the deliberate-breakage check, required once before the milestone is accepted (SC-005, US3 scenario 3): comment out the `GET /` route in `app/routers/pages.py` (or empty `app/templates/pages/home.html`), run `uv run pytest`, confirm the suite **fails**, then `git checkout -- app/` and confirm it passes again

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the remaining cross-cutting quality criteria and leave the tree clean for milestone 2's CI pipeline.

- [ ] T031 Run `uv run ruff format .` then `uv run ruff check .` from repository root and fix every finding, so milestone 2's CI gate starts life on an already-clean tree (research.md D8)
- [ ] T032 [P] Run quickstart.md **V2**: open the page at a ~375 px-wide viewport in the browser device toolbar and confirm text reflows with no horizontal scrollbar (US1 scenario 3, FR-005)
- [ ] T033 [P] Run quickstart.md **V3**: block `/static/css/*` in devtools and reload; confirm the page is unstyled but still structured and readable — never blank, never a wall of unbroken text (edge case: styling assets unavailable)
- [ ] T034 [P] Run quickstart.md **V8**: disconnect from the network, then run `uv run uvicorn app.main:app` and `uv run pytest`; confirm both behave exactly as before, proving no CDN, database or external service is required (FR-010)
- [ ] T035 [P] Verify SC-006 by asking someone unfamiliar with the project to state what the application is for after reading only the home page; revise `APP_DESCRIPTION` in `app/core/config.py` if they cannot
- [ ] T036 Delete `.gitkeep` from directories that now contain real files (`app/core/`, `app/routers/`, `app/static/css/`, `app/templates/layouts/`, `app/templates/pages/`, `tests/integration/`). Keep `.gitkeep` in `app/models/`, `app/schemas/`, `app/services/`, `app/templates/partials/`, `app/static/js/`, `app/static/img/`, `tests/unit/`, `tests/e2e/` and `migrations/` so the mandated layout stays visible (plan.md Structure Decision)
- [ ] T037 Tick every box in the "Milestone acceptance checklist" in `specs/001-hello-world-page/quickstart.md` and confirm each item genuinely passed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (needs the `uv` environment) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational; T024 is only meaningful once US1 exists, since the documented run must end at a visible home page
- **User Story 3 (Phase 5)**: Depends on Foundational; T028 asserts against US1's route and error handler
- **Polish (Phase 6)**: Depends on all three stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent. Can start the moment Phase 2 is done. This is the MVP.
- **User Story 2 (P2)**: The README writing (T022, T023) is independent and can be drafted in parallel with US1. Its verification tasks (T024, T025) need a running page, so they follow US1.
- **User Story 3 (P3)**: Scaffolding (T026, T027) is independent of US1. The assertions in T028 target US1's behaviour, so the story completes after US1.

This dependency direction is inherent to the spec's own priority ordering ("it can only be written once the page exists") and does not compromise each story's independent testability.

### Within Each User Story

- Templates and the router before wiring them into `app/main.py`
- Both `app/main.py` edits (T018, T019) touch one file — run them sequentially, never in parallel
- Manual verification tasks last within their story

### Parallel Opportunities

- T007 runs parallel to the `pyproject.toml` chain (T002–T005 all edit one file and must be sequential)
- **Phase 2 has the widest fan-out**: T009, T010, T011, T012 are four different files with no interdependency
- T015 and T016 are two different template files — parallel
- Phase 6: T032, T033, T034, T035 are independent verifications
- With two developers, one can write the README (T022, T023) while the other builds US1

---

## Parallel Example: Phase 2 (Foundational)

```bash
# After T008, launch the four independent foundational files together:
Task: "Create empty app/core/__init__.py and app/routers/__init__.py"
Task: "Create app/core/config.py with APP_NAME, APP_TAGLINE, APP_DESCRIPTION constants"
Task: "Vendor Pico.css 2.x as app/static/css/pico.min.css"
Task: "Create app/static/css/app.css with minimal project overrides"

# Then T013 (base layout) and T014 (main.py) in sequence.
```

## Parallel Example: User Story 1

```bash
# Launch both templates together:
Task: "Create app/templates/pages/home.html extending layouts/base.html"
Task: "Create app/templates/pages/error.html extending layouts/base.html"

# Then T017 (router), then T018 and T019 sequentially — both edit app/main.py.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T007)
2. Complete Phase 2: Foundational (T008–T014) — CRITICAL, blocks everything
3. Complete Phase 3: User Story 1 (T015–T021)
4. **STOP and VALIDATE**: quickstart V1 and V4 pass — the page renders and unknown paths are friendly
5. This alone satisfies the milestone's "the application starts, the page opens" criterion

### Incremental Delivery

1. Setup + Foundational → the app boots and serves `/static`
2. Add User Story 1 → home page + friendly 404 → **MVP, demoable**
3. Add User Story 2 → documented clean-checkout run → another developer can reproduce it
4. Add User Story 3 → pytest suite → completes the milestone's `_Test:_` criterion
5. Polish → ruff clean, edge cases verified, acceptance checklist ticked

### Parallel Team Strategy

With two developers:

1. Both complete Setup + Foundational together (or one does it while the other reviews the design docs)
2. Then: Developer A takes User Story 1; Developer B drafts the README (US2 T022–T023) and the test scaffolding (US3 T026–T027)
3. Developer B finishes US3's assertions and US2's verification once A's route lands

---

## Notes

- **No HTMX at this milestone.** Plan.md and Principle II are explicit: the page is static content with no partial updates, so HTMX enters with the first interactive feature. `app/templates/partials/` stays empty.
- **No service layer.** There is no business logic to put in one; inventing it now would be an abstraction without a present need (Principle II, YAGNI).
- **No database, no `.env`, no environment variables** — FR-010 requires the app to start with zero configuration.
- Constants are imported into templates and tests from `app/core/config.py`; hard-coding the application name anywhere else breaks the guarantee behind SC-005.
- [P] tasks = different files, no dependencies
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
