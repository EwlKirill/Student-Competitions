# HTTP Contract: Hello World Page (Milestone 1)

**Feature**: `001-hello-world-page` | **Date**: 2026-09-21 | **Plan**: [plan.md](../plan.md)

The application's entire external interface at this milestone is the HTTP surface below. There is
no JSON API, no HTMX fragment endpoint and no authentication. Every response is anonymous and
identical for all visitors.

Base address for a local run: `http://127.0.0.1:8000`.

---

## `GET /` — home page

**Purpose**: Serve the single server-rendered home page (FR-001, FR-003).

**Request**: no parameters, no headers required, no cookies read.

**Response `200 OK`**

| Aspect | Contract |
|---|---|
| `Content-Type` | `text/html; charset=utf-8` |
| Rendering | Complete HTML produced on the server; the document is meaningful with JavaScript disabled (FR-003) |
| `<title>` | Non-empty and contains `APP_NAME` (FR-004) |
| `<h1>` | Contains `APP_NAME` (FR-002) |
| Body copy | Contains `APP_DESCRIPTION` — one or two sentences stating the application's purpose (FR-002, SC-006) |
| `<head>` | Includes `<meta name="viewport" content="width=device-width, initial-scale=1">` (FR-005) |
| Stylesheets | `<link>` to `/static/css/pico.min.css` then `/static/css/app.css`, in that order |
| Degradation | Semantic elements (`<header>`, `<main>`, `<h1>`, `<p>`) carry the structure, so the page stays readable if either stylesheet fails to load |
| Caching | None specified; default framework headers are acceptable |

**Errors**: none. This route has no failure mode of its own — it reads no input, touches no
database and calls no external service (FR-010).

**Template**: `app/templates/pages/home.html`, extending `app/templates/layouts/base.html`.
Context: see [data-model.md](../data-model.md#template-context).

---

## `GET /static/{path}` — static assets

**Purpose**: Serve the vendored stylesheet and any future local asset. Mounted with Starlette's
`StaticFiles` on the directory `app/static`.

| Case | Status | Body |
|---|---|---|
| Existing file, e.g. `/static/css/pico.min.css` | `200 OK` | File contents with the type inferred from the extension (`text/css` for `.css`) |
| Missing file under `/static/` | `404 Not Found` | Starlette's static-file 404 |

No directory listing is exposed, and nothing outside `app/static` is reachable through this mount.

---

## Any unmatched path — friendly "not found"

**Purpose**: Satisfy FR-006 and the constitution's rule that user-facing errors render a friendly
page rather than a stack trace or raw JSON.

**Trigger**: any request whose path matches no route — the spec's example is `GET /about` — which
Starlette raises as an `HTTPException(404)`.

**Response `404 Not Found`**

| Aspect | Contract |
|---|---|
| `Content-Type` | `text/html; charset=utf-8` |
| Status | The original exception's status code, unchanged (`404` here) |
| Body | Rendered `app/templates/pages/error.html`: the status code, a short human-readable message, and a link back to `/` |
| Forbidden content | No stack trace, no framework debug output, no internal path |

**Scope**: the handler is registered for `HTTPException` generally, not only `404`, so routes added
in later milestones inherit the same friendly page. It returns HTML unconditionally at this
milestone — there is no JSON API to content-negotiate against yet.

---

## Routes deliberately absent

| Not implemented | Arrives in |
|---|---|
| Any page other than `/` | later milestones (explicitly out of scope per the spec) |
| Health/readiness endpoint | milestone 2, with deployment |
| HTMX partial endpoints (`templates/partials/`) | the first interactive feature |
| Auth routes (login, OTP, logout) | milestone 4 |
| Any JSON API | not planned — the UI is server-rendered (Principle II) |

## Contract verification

The contract is verified at two levels. Not every row above is asserted in code — this table says
which are, so the distinction is not mistaken for coverage that exists.

**Asserted by `tests/integration/test_home.py`:**

| Contract row | Assertion |
|---|---|
| `GET /` status | `200` |
| `GET /` `Content-Type` | `text/html; charset=utf-8` |
| `<title>` non-empty | a non-empty `<title>` is present |
| Body carries the app name | body contains `APP_NAME`, imported from `app.core.config` (and `APP_NAME` is truthy, so the containment check cannot pass vacuously) |
| Viewport meta | `<meta name="viewport" content="width=device-width, initial-scale=1">` is in the `<head>` |
| Unmatched path | `GET /about` returns `404` and renders HTML |

**Verified manually via [quickstart.md](../quickstart.md), not by the suite:**

| Contract row | Where |
|---|---|
| `<title>` *contains* `APP_NAME` (the test checks only that it is non-empty) | V1 — the browser tab |
| `<h1>` contains `APP_NAME`, body copy contains `APP_DESCRIPTION` | V1 |
| Server-side rendering — complete HTML, not a JS shell | V1 step 3 (`curl` piped to `head -40`) |
| Stylesheet `<link>` order: `pico.min.css` then `app.css` | V1 (page source) |
| Degradation when a stylesheet fails to load | V3 |
| `GET /static/css/pico.min.css` → `200 text/css`; no directory listing | Phase 2 checkpoint (`curl -I`) |
| Error page forbidden content (no stack trace, debug output or internal path) | V4, in the browser |

Any row in the second table that later becomes cheap to assert — most of them are one line against
the response text — should move up rather than stay manual.
