# HTTP Contract: Database & First Entity — Questions (Milestone 3)

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](../plan.md)

This milestone changes the HTTP surface in exactly one way: **`GET /` gains a read-only question
list and a database status line.** No route is added. `/healthz`, the static mount and the
friendly error page keep their
[milestone 2 contract](../../002-public-deploy-cicd/contracts/http-routes.md) unchanged.

---

## `GET /` — home page

**Request**: no parameters, no cookies read, no authentication (unchanged).

**Handler**: `app/routers/pages.py::home`, now a sync `def` with a `Session` dependency. It calls
`list_questions` and `read_database_status`, maps questions to `QuestionPublic`, and renders
`pages/home.html`. No business logic in the handler or template (constitution *Application
Layout*).

### Response `200 OK`: database reachable

| Aspect | Contract |
|---|---|
| `Content-Type` | `text/html; charset=utf-8` (unchanged) |
| Milestone 1 content | Unchanged: `<h1>` is the application name, tagline and description follow, `<title>` and viewport meta as before (FR-021) |
| Questions section | `<section id="questions" aria-labelledby="questions-heading">` with `<h2 id="questions-heading">Sample questions</h2>` |
| Question list | `<ol class="question-list">` with one `<li>` per stored question, containing **only** that question's text, in `created_at, id` order (FR-016, FR-021). Each question appears exactly once (US1 scenario 4). |
| Empty state | When no questions are stored: `<p class="questions-empty">No questions yet.</p>` in place of the `<ol>` (FR-023) |
| Escaping | Question text is autoescaped: `<b>` arrives as `&lt;b&gt;`, `&` as `&amp;` (FR-024). No `\|safe` filter is used on any database value. |
| Line breaks & wrapping | `white-space: pre-line` and `overflow-wrap: anywhere` on list items; no horizontal page scroll at phone width (spec edge cases) |
| Reference answers | **Never present** in the response body in any form (FR-022). The template receives `QuestionPublic`, which has no such field. |
| Write affordances | **None**: no `<form>`, no `<button>`, no link to a create/edit/delete address (FR-018, US1 scenario 2) |
| Status line | One element, specified below (FR-025) |
| Side effects | None. **No write** to the database on a page view; the boot count does not change (FR-028) |
| Latency | Under 3 s warm on the public address, and locally with 500 questions (SC-005) |

**Status line markup** (the attributes are the machine contract; the text is for people):

```html
<p class="db-status"
   data-engine="postgresql" data-revision="3f2a9c1b7d4e" data-boots="14">
  Database: PostgreSQL · schema revision <code>3f2a9c1b7d4e</code> · boot #14
</p>
```

| Attribute | Value | Consumers |
|---|---|---|
| `data-engine` | SQLAlchemy dialect name: `sqlite` or `postgresql` | tests; CI `image` smoke test |
| `data-revision` | Current `alembic_version.version_num` | tests; `scripts/database_status.sh verify` in the deploy job |
| `data-boots` | `boot_counter.boots`, decimal integer | tests; CI `image` smoke test (restart → +1); deploy job (strictly higher after release) |

Display names: `sqlite` → "SQLite", `postgresql` → "PostgreSQL". The status line lives in the
home page, placed after the question section and before the shared layout's release footer. The
error page does not show it.

### Response `200 OK`: database unreachable at request time

| Aspect | Contract |
|---|---|
| Status | Still `200`, and the page still renders with layout, hero and footer (FR-026) |
| In place of the list **and** the status line | `<p class="data-unavailable" role="status">Question data is temporarily unavailable. Please try again in a moment.</p>` |
| Error detail | None in the body: no exception text, no SQL, no host name, no stack trace (FR-026) |
| Logging | One log record at `ERROR` with the exception type and message. Never the database URL (FR-032) |
| Trigger | Any `sqlalchemy.exc.SQLAlchemyError` raised by the two reads. Anything else still reaches the default `500` handling (a bug, not a blip) |

### Errors

Unchanged: unmatched paths render the friendly error page (milestone 1).

---

## `GET /healthz`: unchanged, and now explicitly independent of the database

The milestone 2 contract holds byte for byte: `200`, `application/json`, exactly
`{"status","version","commit"}`, **no I/O** (FR-029). New in this milestone, as a test rather than
a change: `/healthz` returns `200` while every database read on `/` is failing. Liveness never
depends on the database, so Render does not restart-loop the service during a database blip.

---

## Application startup: the effective readiness gate

Not a route, but it decides when routes exist. Uvicorn binds the port only after `lifespan`
startup succeeds, which requires, in order:

1. `resolve_database_url(os.environ)` succeeds (FR-004): see [configuration.md](./configuration.md);
2. the database's current revision equals the head of `migrations/`, otherwise startup fails with
   the `uv run alembic upgrade head` instruction;
3. the boot increment updates exactly one row (FR-027).

Any failure → uvicorn exits non-zero → the instance never answers `/healthz` → Render keeps the
previous release ([research D11](../research.md#d11--liveness-vs-readiness-no-new-endpoint)).

---

## Routes deliberately absent (FR-018, FR-033)

| Not implemented | Arrives in | Guarded by |
|---|---|---|
| Any `POST`/`PUT`/`PATCH`/`DELETE` route | Milestone 4 (login), milestone 6 (question bank) | `tests/integration/test_routes.py`: every registered route's methods are a subset of `{GET, HEAD}` |
| Question detail page, JSON question API | Not planned as JSON; question pages in milestone 6 | Same test, plus the list items contain no links |
| A readiness endpoint | Not planned (research D11) | none needed |
