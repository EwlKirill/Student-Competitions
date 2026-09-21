# Quickstart & Validation: Hello World Page (Milestone 1)

**Feature**: `001-hello-world-page` | **Date**: 2026-09-21 | **Plan**: [plan.md](./plan.md)

How to run the application and prove this milestone is done. Every scenario below maps to an
acceptance scenario or success criterion in [spec.md](./spec.md). These same commands belong in
the README's "Getting started" section (FR-009).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed. Nothing else — **no system Python is required**:
  `uv` reads `.python-version` and provisions Python 3.13 itself.
- No database, no `.env` file, no API keys, no network access after dependencies are installed
  (FR-010).

## Setup

```bash
git clone <repository-url>
cd Student-Competitions
uv sync
```

`uv sync` creates `.venv/`, installs the locked dependencies and downloads Python 3.13 if it is
not already present. Expected: it finishes without prompting for anything.

## Run

```bash
uv run uvicorn app.main:app --reload
```

Expected output ends with a line naming the address it is serving on:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open <http://127.0.0.1:8000> in a browser.

## Test

```bash
uv run pytest
```

Expected: all tests pass in well under 30 seconds (SC-004).

## Lint & format

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: both clean. These become CI gates in milestone 2; keeping them green now means that
pipeline starts life passing.

---

## Validation scenarios

### V1 — Home page renders (US1 scenarios 1–2; FR-001…FR-004; SC-002)

1. Start the application and open <http://127.0.0.1:8000>.
2. **Expected**: a styled page showing the application name as a heading and a one- or two-sentence
   description of what the application is for; the browser tab shows a descriptive title.
3. Confirm the HTML really comes from the server:

   ```bash
   curl -s http://127.0.0.1:8000 | head -40
   ```

   **Expected**: complete HTML including the application name and description — not an empty
   shell that JavaScript would fill in (FR-003).

### V2 — Readable on a phone-width screen (US1 scenario 3; FR-005)

1. Open the page, then open the browser's device toolbar and select a ~375 px-wide viewport.
2. **Expected**: text reflows and stays readable; no horizontal scrollbar appears.

### V3 — Readable without styling (edge case: styling assets unavailable)

1. With the app running, request the page with the stylesheet blocked — in the browser devtools
   Network panel, block `/static/css/*` and reload.
2. **Expected**: the page is unstyled but still structured and readable — heading, then
   description — never a blank screen or a wall of unbroken text.

### V4 — Unknown path returns a friendly "not found" (edge case; FR-006)

```bash
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:8000/about
```

**Expected**: `404 text/html; charset=utf-8`. Opening <http://127.0.0.1:8000/about> in a browser
shows a styled "not found" page with a link home — no stack trace, no raw JSON.

### V5 — Clean checkout to running page (US2; SC-001, SC-003)

1. Clone into a fresh directory and follow **Setup** → **Run** using only the documented commands.
2. **Expected**: from clone to a visible home page in under 10 minutes, and the page itself
   appears in under 2 seconds once the server is up.
3. **Expected**: the README contains these setup, run and test commands (FR-009, US2 scenario 3).

### V6 — Port already in use (edge case)

1. With the application already running, start a second instance in another terminal with the same
   command.
2. **Expected**: it exits with a clear error naming the address —
   `[Errno 48] Address already in use` (errno 98 on Linux) — not a silent failure or a hang.
   Starting on another port (`--port 8001`) works.

### V7 — The test suite really covers the page (US3; FR-008; SC-004, SC-005)

1. Run `uv run pytest -v`.
2. **Expected**: the listed tests include one asserting that `GET /` returns `200` with the
   application name in the response body, and one asserting an unknown path returns `404`.
3. **Prove the test would catch a regression** (SC-005) — this check is required once before the
   milestone is accepted:
   - Temporarily break the home page: comment out the `GET /` route in `app/routers/pages.py`,
     or empty `app/templates/pages/home.html`.
   - Run `uv run pytest`.
   - **Expected**: the suite **fails**.
   - Revert the change with `git checkout -- app/` and confirm `uv run pytest` passes again.

### V8 — No hidden external dependency (FR-010)

1. Stop the app, disconnect from the network (or disable Wi-Fi), then run
   `uv run uvicorn app.main:app` and `uv run pytest` again.
2. **Expected**: both work exactly as before. Dependencies are already installed, and neither the
   application nor its tests contact any external service, database or CDN.

---

## Milestone acceptance checklist

The milestone's stated criterion is *"the application starts, the page opens, there is a first
pytest test for the endpoint."* It is met when:

- [ ] V1 passes — the home page renders server-side with name and description.
- [ ] V4 passes — unknown paths return a friendly 404.
- [ ] V5 passes — a clean checkout reaches the page using only documented commands.
- [ ] V7 passes, including the deliberate-breakage step.
- [ ] `uv run ruff check .` and `uv run ruff format --check .` are clean.
- [ ] `uv.lock` is committed alongside `pyproject.toml`.
- [ ] The README documents setup, run and test commands.

## Reference

- HTTP surface: [contracts/http-routes.md](./contracts/http-routes.md)
- Template context and constants: [data-model.md](./data-model.md)
- Decisions and rejected alternatives: [research.md](./research.md)
