# Data Model: Hello World Page (Milestone 1)

**Feature**: `001-hello-world-page` | **Date**: 2026-09-21 | **Plan**: [plan.md](./plan.md)

## Persisted entities

**None.** This milestone stores nothing.

There is no database, no ORM, no session state and no file written at runtime. The spec's
"Key Entities" section was removed for exactly this reason, and FR-010 forbids requiring a
database to start. SQLModel tables (`app/models/`), Pydantic schemas (`app/schemas/`) and Alembic
migrations (`migrations/`) all stay empty until milestone 3 introduces the `Question` entity.

Consequences that later milestones inherit:

- No Alembic migration accompanies this feature's pull request (the constitution's PR gate for
  schema changes does not apply).
- Nothing in `app/` imports a database engine, so the application starts with no connection
  string and no network access.
- The first real data model decision — timezone-aware UTC timestamps, SQLite/PostgreSQL parity —
  is made in milestone 3, not pre-empted here.

## View model (non-persisted)

The only structured data in the feature is the context dictionary handed to Jinja2. It is defined
by three constants in `app/core/config.py` and is the single source of truth for the strings that
appear on the page, in the browser tab, and in the test assertions.

### `app/core/config.py` constants

| Constant | Type | Value shape | Used by | Requirement |
|---|---|---|---|---|
| `APP_NAME` | `str` | Short product name, e.g. `"Student Competitions"` | `<title>`, `<h1>`, `test_home.py` | FR-002, FR-004, FR-008 |
| `APP_TAGLINE` | `str` | One short line under the name | home page hero | FR-002 |
| `APP_DESCRIPTION` | `str` | One or two sentences stating what the application is for | home page body, `<meta name="description">` | FR-002, SC-006 |

Validation rules:

- All three MUST be non-empty. There is no runtime validation — a non-empty `APP_NAME` is proven
  by the integration test asserting it appears in the rendered HTML, and an empty string would
  make that assertion vacuous, so the test also asserts `APP_NAME` is truthy.
- `APP_DESCRIPTION` MUST read as plain prose to someone who has never seen the project (SC-006).
- Values are literals, not read from the environment: FR-010 requires the app to start with no
  configuration. Environment-backed settings arrive with milestone 2's deployment work.

### Template context

`GET /` renders `pages/home.html` with:

```python
{"app_name": APP_NAME, "app_tagline": APP_TAGLINE, "app_description": APP_DESCRIPTION}
```

The error page renders `pages/error.html` with:

```python
{"app_name": APP_NAME, "status_code": <int>, "detail": <str>}
```

`request` is supplied by `Jinja2Templates` and is required by Starlette's template response.

### Relationships and state

None. There are no relationships between these values and no state transitions — the page is
identical on every request, for every visitor, for the lifetime of the process. Nothing in this
milestone mutates, so there is no lifecycle to document.

See [contracts/http-routes.md](./contracts/http-routes.md) for how this view model reaches the
browser.
