# Research: Hello World Page (Milestone 1)

**Feature**: `001-hello-world-page` | **Date**: 2026-09-21 | **Plan**: [plan.md](./plan.md)

The constitution already fixes the stack (Python + FastAPI, Jinja2, Pico.css, uv, ruff, pytest),
so this phase resolves only what the constitution and the spec leave open. One item was a formal
`NEEDS CLARIFICATION` (the Python version, which the constitution assigns to milestone 1); the
rest are the small implementation choices that follow from the spec's constraints.

**Status**: all open items resolved — no `NEEDS CLARIFICATION` remains.

---

## D1: Python version

**Decision**: **Python 3.13**, pinned in `.python-version` (`3.13`) and in `pyproject.toml`
(`requires-python = ">=3.13,<3.14"`). `uv` provisions the interpreter, so contributors do not
need a matching system Python.

**Rationale**: This is the constitution's one *open stack decision* for milestone 1, and it binds
every later milestone. 3.13 is the current stable-minus-one release: mature, supported well past
this project's horizon, and the version with the broadest prebuilt-wheel coverage for the
dependencies that arrive later in the ladder (the PostgreSQL driver in milestone 3, Playwright in
milestone 12). It is a first-class runtime on Render and in the official slim container images,
which milestone 2 will need. Pinning an upper bound keeps the production container, CI and every
developer machine on one minor version rather than drifting silently.

**Alternatives considered**:

- **3.14** — the latest stable, and the interpreter already installed on the author's machine.
  Rejected: it buys nothing this stack uses today, while raising the chance that a later
  dependency has no wheel yet and forces a source build in CI or in the deploy image. Because
  `uv` downloads the pinned interpreter, matching the local machine has no practical value.
- **3.12** — maximum ecosystem compatibility. Rejected: nothing in the stack requires it, and it
  gives up two releases of typing and performance work for a risk that does not exist.

---

## D2: ASGI server and start command

**Decision**: `uvicorn[standard]` as a runtime dependency, started with
`uv run uvicorn app.main:app --reload`. The documented address is `http://127.0.0.1:8000`.

**Rationale**: FastAPI ships no server, so something must satisfy FR-007 ("start with a documented
command and report the local address"). Uvicorn is FastAPI's documented default, prints the
address it binds to on startup, and prints a clear `[Errno 48] Address already in use` error when
the port is taken — which covers the spec's "port already in use" edge case with no code of our
own. The `[standard]` extra adds the faster HTTP/websocket implementations and `--reload`
watching. `app.main:app` is the import path the milestone-2 Dockerfile and Render start command
will reuse unchanged.

**Alternatives considered**:

- **`fastapi[standard]` + `fastapi dev`** — one dependency line, nicer dev output. Rejected: it
  pulls in extras this milestone does not use (`python-multipart`, `email-validator`,
  `fastapi-cli`), which works against the constitution's rule that every runtime dependency be
  justified. Declaring `fastapi`, `uvicorn` and `jinja2` explicitly keeps each one accountable.
- **Hypercorn / Granian** — no advantage for this workload and off the documented FastAPI path.

---

## D3: Pico.css delivery — vendored, not CDN

**Decision**: Commit `pico.min.css` (Pico.css 2.x, **full build**) to
`app/static/css/`, mount `app/static` at `/static` with Starlette's `StaticFiles`, and link it
from the base layout. Project-specific overrides live in a separate, deliberately small
`app/static/css/app.css`.

**Rationale**: FR-010 and the spec's "no network access when running locally" edge case rule out a
CDN link — a CDN-styled page is a page that breaks on a plane or behind a restrictive network.
Vendoring also makes the styling deterministic and version-controlled, and keeps the promise of
"no CSS build step" (the constitution's styling row): the file is served as-is. Keeping overrides
in a second file preserves the upgrade path — replacing `pico.min.css` never clobbers our changes.

**Alternatives considered**:

- **CDN `<link>`** — zero bytes in the repo. Rejected: violates FR-010 and the offline edge case.
- **npm/`uv`-installed Pico plus a copy step** — a build step the constitution forbids.
- **Pico's classless build (`pico.classless.min.css`)** — styles `body > header`/`main`/`footer`
  as containers with no class names at all, which is marginally more minimal today. Rejected:
  it drops `.container`, `.grid` and the other layout classes that milestone 2+ pages and HTMX
  partials will want, and switching builds later means re-auditing every template that grew a
  class in the meantime. Both builds style semantic elements without classes, so the
  "styling assets unavailable" degradation argument below is unaffected by the choice.

**Follow-on requirement**: because the stylesheet can still fail to load (the spec's "styling
assets unavailable" edge case), the templates use semantic HTML — `<header>`, `<main>`, `<h1>`,
`<p>` — so the unstyled page is still readable, structured text. Pico.css styles those elements
without class names, so no class-name scaffolding is needed either way.

---

## D4: Responsive, readable layout without custom CSS

**Decision**: Rely on Pico.css's container and typography defaults, plus
`<meta name="viewport" content="width=device-width, initial-scale=1">` in the base layout. Keep
`app.css` limited to the few cosmetic touches the home page needs (e.g. vertical centering of the
hero block).

**Rationale**: FR-005 requires a readable layout on desktop and phone widths, and SC-006 requires
a first-time reader to understand the product from the page alone. Pico's `<main class="container">`
already gives fluid max-widths, readable measure and a mobile-first type scale, so the requirement
is met by the stack's default rather than by hand-written media queries. Writing our own
responsive CSS at this milestone would be an abstraction with no present need.

**Alternatives considered**: custom CSS grid/flex layout — rejected as unnecessary work that
duplicates what Pico.css already provides, and as a maintenance cost for later milestones.

---

## D5: "Not found" handling

**Decision**: Register a Starlette `HTTPException` handler in `app/main.py` that renders
`templates/pages/error.html` with the response's status code and a short message, returning the
original status code. This turns FastAPI's default JSON `{"detail": "Not Found"}` into a styled
HTML page for `GET /about` and any other unknown path.

**Rationale**: FR-006 requires a "not found" response rather than an unhandled error, and the
constitution's *Operational Constraints* require user-facing errors to render a friendly page
with no stack trace. Handling `HTTPException` generically (rather than only 404) means the
milestone-2+ routes inherit the friendly page for free, at the cost of about five lines. The
handler returns HTML unconditionally at this milestone — there is no API surface yet to
content-negotiate against; when JSON endpoints appear, the handler grows an `Accept` check.

**Alternatives considered**:

- **Leave FastAPI's JSON default** — satisfies FR-006 literally but shows raw JSON to a browser
  visitor, which conflicts with the constitution's friendly-error rule.
- **A catch-all route (`/{path:path}`)** — rejected: it would shadow real routes added later and
  is a well-known source of routing bugs.

---

## D6: Where the application name and description live

**Decision**: Three module-level constants — `APP_NAME`, `APP_TAGLINE`, `APP_DESCRIPTION` — in
`app/core/config.py`, passed into the template context by the router. No `pydantic-settings`, no
`.env`, no environment variables at this milestone.

**Rationale**: FR-002 and FR-004 put the same strings in the page body, the `<title>` and the
test's assertion. A single source keeps the test honest — asserting against the constant proves
the page renders *the* application name, not a copy that drifted. Putting them in `core/` matches
the constitution's layout (settings live in `core/`) and gives milestone 2 an obvious place to
introduce environment-backed settings when there is finally something to configure. Introducing
`pydantic-settings` now would add a runtime dependency with zero settings to read (FR-010 says the
app must start with no configuration).

**Alternatives considered**:

- **Hard-code the strings in the template** — rejected: the test would then assert a duplicated
  literal, which passes even if the page is wrong.
- **`pydantic-settings` + `.env` now** — rejected as premature; nothing is configurable yet.

---

## D7: Test placement, shape and the FastAPI test client

**Decision**: `tests/conftest.py` exposes a session-scoped `client` fixture wrapping
`fastapi.testclient.TestClient(app)`. The assertions live in `tests/integration/test_home.py` and
cover: root returns `200`; `Content-Type` is `text/html`; the body contains `APP_NAME` and a
non-empty `<title>`; an unknown path (`/about`) returns `404` and renders HTML. Run with
`uv run pytest`. `httpx` is a dev dependency because `TestClient` requires it.

**Rationale**: The constitution puts "HTTP routes via the FastAPI test client" in
`tests/integration/`, so that is where the milestone's `_Test:_` criterion belongs; `tests/unit/`
stays empty because there is no pure logic to test yet, and inventing a unit test for a constant
would be noise. `TestClient` exercises the real ASGI app — routing, template rendering and the
error handler — without binding a port, which keeps the suite fast (SC-004: under 30 s) and free
of the "port in use" flakiness a live-server test would introduce. Asserting against the imported
`APP_NAME` constant rather than a hard-coded string is what makes SC-005 true: delete or break the
home page and the suite fails.

**Alternatives considered**:

- **Live `uvicorn` subprocess + real HTTP requests** — closer to production but slower and flaky;
  it belongs to the Playwright e2e tier in milestone 12.
- **`httpx.ASGITransport` directly** — equivalent, but `TestClient` is the documented FastAPI path
  and reads better for a project that is also a teaching artifact.

---

## D8: Lint and format configuration

**Decision**: Configure `ruff` in `pyproject.toml` with `target-version = "py313"`,
`line-length = 100`, and a lint rule selection covering pycodestyle/pyflakes, isort, pyupgrade and
bugbear (`E`, `F`, `I`, `UP`, `B`). Run locally as `uv run ruff check .` and
`uv run ruff format .`.

**Rationale**: The constitution names ruff as the only linter/formatter and makes
`ruff check` + `ruff format --check` a CI gate from milestone 2. Configuring it now — one
milestone before it is enforced — means milestone 2's pipeline turns green on an already-clean
tree instead of arriving with a formatting diff attached. The rule set is intentionally small;
it can grow when the codebase does.

**Alternatives considered**: deferring all ruff config to milestone 2 — rejected, since the stack
table already places ruff in milestone 1 and a late first format touches every file at once.
