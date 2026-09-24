# Configuration Contract: where the database is, and when to refuse to start

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](../plan.md)

One function, `resolve_database_url(environ: Mapping[str, str] = os.environ) -> str` in
`app/core/config.py`, decides the database location. The application's `lifespan` and
`migrations/env.py` both call it, so the app and its migrations always target the same database.
Rationale: [research D3](../research.md#d3--database-configuration-database_url-a-local-default-and-a-production-guard).

---

## Inputs

| Variable | Meaning | Documented in README (FR-032) |
|---|---|---|
| `DATABASE_URL` | Database location. Supported schemes: `sqlite`, `postgres`, `postgresql`, `postgresql+psycopg`. Empty string is treated as unset. | yes: purpose, default, "secret in production" |
| `RENDER` | Presence means "running on Render" (Render sets it to `true`). Any non-empty value triggers the guard. | yes: "set by Render; do not set it locally" |
| `TEST_POSTGRES_URL` | **Tests only.** A PostgreSQL server URL whose role may `CREATE DATABASE`. Never read by the application. | yes: how to run the PostgreSQL half of the suite |

## Outputs

| Case | Result |
|---|---|
| `DATABASE_URL=sqlite:///…` | returned unchanged |
| `DATABASE_URL=postgres://…` or `postgresql://…` | scheme rewritten to `postgresql+psycopg://`; user, password, host, port, database and query string (`sslmode`, `channel_binding`) preserved exactly |
| `DATABASE_URL=postgresql+psycopg://…` | returned unchanged |
| `DATABASE_URL` unset or empty, `RENDER` unset | `sqlite:///<project root>/data/student_competitions.sqlite3`; `<project root>` is the parent of the `app` package (the repository root locally, `/app` in the image). `data/` is created if missing. |
| `DATABASE_URL` unset or empty, `RENDER` set | raises `DatabaseConfigError` (see below) |
| `DATABASE_URL` unparseable | raises `DatabaseConfigError` |
| `DATABASE_URL` with any other scheme (`mysql://`, `sqlite+aiosqlite://`, …) | raises `DatabaseConfigError` |

## Errors

`DatabaseConfigError` subclasses `RuntimeError`. Its message **never contains the URL or any part
of it** (no user, no password, no host), and the original parse exception is suppressed
(`raise … from None`) so it does not appear in the traceback (FR-004, FR-032, SC-010).

| Case | Message (exact wording may vary; the content may not) |
|---|---|
| On Render without a URL | `DATABASE_URL is required when running on Render; refusing to fall back to a local SQLite file.` |
| Unparseable | `DATABASE_URL is not a valid database URL.` |
| Unsupported scheme | `DATABASE_URL uses unsupported scheme '<scheme>'; expected sqlite or postgresql.` (the scheme only) |

**Where an error surfaces**:

| Process | Effect |
|---|---|
| `alembic upgrade head` (entrypoint, or a developer) | exits non-zero with the message; nothing is migrated |
| uvicorn `lifespan` startup | the application does not start; uvicorn exits non-zero |
| On Render | the new instance never passes `/healthz`; the deploy fails; the previous release keeps serving |

## Portability note

The guard keys on `RENDER` because Render is the recorded host (milestone 2 D1). Moving to one of
the constitution's approved alternatives means adding that platform's equivalent always-set
variable (for example `RAILWAY_ENVIRONMENT` or `FLY_APP_NAME`) to the guard, in the same pull
request as the move.

## Verification

| Check | Where |
|---|---|
| Every row of *Outputs* and *Errors*, and "message contains no part of the URL" for a URL with a recognisable password | `tests/unit/test_database_config.py` |
| The packaged app refuses to start with `RENDER=true` and no `DATABASE_URL`, and says why | CI `image` job ([pipeline.md](./pipeline.md)) |
| `postgresql://` from Neon/CI works in the real image | CI `image` job runs with the un-normalised form |
