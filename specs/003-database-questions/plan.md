# Implementation Plan: Database & First Entity — Questions (Milestone 3)

**Branch**: `003-database-questions` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-database-questions/spec.md`

## Summary

Give the application a database and put the first product entity, the **question**, into it.

**Storage**: locally, a SQLite file at `data/student_competitions.sqlite3`, used when no
configuration is given. In production, a **Neon free-plan PostgreSQL 17** database in Frankfurt,
next to the Render service. Its connection string lives only in Render's environment as
`DATABASE_URL`. One function resolves the location for both the app and its migrations. It
refuses to fall back to SQLite when running on Render, so a missing credential fails the release
instead of silently losing data.

**Migrations**: SQLModel models in `app/models/` (`Question`, `BootCounter`) and Alembic
migrations in `migrations/`. The second migration **seeds six sample questions**, so they exist
exactly once per database with no startup logic. The container entrypoint becomes
`alembic upgrade head && exec uvicorn …`, because Render's pre-deploy command is not available on
the free plan. A failed migration never lets uvicorn bind, so Render keeps the previous release.
On PostgreSQL, the whole upgrade is one transaction behind an advisory lock, so it is
all-or-nothing and safe when two instances overlap. At startup the app also refuses to run
against a database that is not at head.

**Code**: an internal service, `app/services/questions.py` (create, get, list, update, delete,
with `QuestionNotFound`), guarded by `QuestionCreate`/`QuestionUpdate` schemas that trim and
length-check input. No route writes anything. The home page gains a read-only question list
(question text only, via `QuestionPublic`) and a status line,
`Database: PostgreSQL · schema revision 3f2a… · boot #14`. It carries `data-*` attributes for
machines. The boot count is one row incremented atomically once per application start. If the
database fails mid-request, the page renders with a friendly notice while `/healthz` stays
I/O-free and green.

**Verification**: every database-touching test runs on **both engines** through one
parametrized fixture. Each test gets its own clone of a migrated template database. CI adds a
password-less `postgres:17` service. The `image` job now boots the real container against
PostgreSQL, restarts it, and asserts the boot count went 1 → 2. Every release's deploy job asserts
that the public page shows the new head revision and a strictly higher boot count, which turns the
milestone's production criterion into a check made on every release.

## Technical Context

**Language/Version**: Python 3.13, unchanged (`.python-version`, `requires-python = ">=3.13,<3.14"`).

**Primary Dependencies**: FastAPI, Jinja2 and uvicorn, unchanged. **New runtime**: `sqlmodel`
(0.0.47, brings SQLAlchemy 2.0.54), `alembic` (1.20.0) and `psycopg[binary]` (3.3.6). All three
are scheduled by the constitution for milestone 3 and justified below. **No new dev dependency.**
The PostgreSQL test server comes from a URL, not a library ([research D2](./research.md#d2--orm-migrations-and-driver-sqlmodel-sync--alembic--psycopg-3),
[D12](./research.md#d12--tests-on-both-engines-one-parametrized-fixture-template-and-clone-isolation)).

**Storage**: SQLite (built-in `sqlite3`) locally and in tests; PostgreSQL 17 on **Neon free plan**,
`aws-eu-central-1`, direct endpoint, in production; `postgres:17` service containers in CI
([research D1](./research.md#d1--managed-production-postgresql-neon-free-plan)). Three tables:
`questions`, `boot_counter` and Alembic's `alembic_version` ([data-model.md](./data-model.md)).

**Testing**: pytest with FastAPI's `TestClient`, as before. A parametrized `database_url` fixture
runs every database test on `[sqlite]` and `[postgresql]`. Isolation comes from migrate-once,
clone-per-test (file copy / `CREATE DATABASE … TEMPLATE`). PostgreSQL cases are skipped locally
without `TEST_POSTGRES_URL` and required when `CI=true`. New modules:
`tests/unit/test_database_config.py`, `tests/unit/test_question_schemas.py`,
`tests/integration/test_question_service.py`, `test_migrations.py`, `test_boot_counter.py`,
`test_startup.py` and `test_routes.py`. Existing `test_home.py` and `test_health.py` are extended.

**Target Platform**: Linux container on Render (free web service, `frankfurt`), unchanged. It
connects over TLS to Neon in the same city. The same image runs locally with a throw-away SQLite
file, or with `DATABASE_URL` pointing at any PostgreSQL.

**Project Type**: single server-rendered web application, unchanged.

**Performance Goals**: home page under 3 s warm on the public address, and under 3 s locally with
500 questions (SC-005). The page runs three small queries. PR verification stays under 10 minutes
with both engines (SC-009); the PostgreSQL services add about 10–20 s per job.

**Constraints**:

- Render free tier: no pre-deploy command (so migrations run in the entrypoint), no persistent
  disk (so production data must be off-box), 5-second health-check budget (so `/healthz` stays
  I/O-free), single instance that may overlap briefly on deploy (so migrations are locked and
  backward compatible).
- Neon free tier: compute suspends when idle, so connections are pre-pinged; storage and compute
  allowances are far above need; re-check at bootstrap.
- Same models and migrations on both engines (FR-005). One PostgreSQL-specific feature, the
  migration advisory lock, is justified in Complexity Tracking.
- No database credential in the repository, the image, GitHub, or any log (FR-032, SC-010).
- No write route of any kind (FR-018, FR-033).

**Scale/Scope**: 2 models, 3 schemas, 2 services, 2 migrations, about 6 new application modules,
1 new script, 5 changed infrastructure files, 7 new or extended test modules, README updates.
Data volume: 6 seed rows; the product's lifetime data stays in megabytes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Verdict | Evidence / Notes |
|---|---|---|---|
| I | Walking Skeleton & Vertical Slices | **PASS** | Milestone 3 of the ladder, on branch `003-database-questions`, started after milestone 2 was merged, deployed and verified (commits `7fcdc71`, `177922c`). It is a vertical slice: models → migrations → service → page → public address, visible to anyone as the question list and a boot count that rises. It is not a horizontal "all models" layer: only the one entity the ladder names, plus the counter that makes persistence observable. Nothing from later milestones is built: no users, auth, roles, competitions, or write routes (FR-033). |
| II | Server-Rendered Simplicity | **PASS** | The home page stays server-rendered Jinja2 with Pico.css; two CSS rules are added to `app.css` (line breaks, wrapping). No HTMX partial and no JavaScript is needed, because nothing is interactive. The three **new runtime dependencies** (`sqlmodel`, `alembic`, `psycopg[binary]`) are justified in the table below. Services are plain functions, with no repository class or unit-of-work abstraction, because each would have one implementation (YAGNI). `pydantic-settings` is still not added ([research D2](./research.md#d2--orm-migrations-and-driver-sqlmodel-sync--alembic--psycopg-3)). |
| III | Test-Backed Delivery (NON-NEGOTIABLE) | **PASS** | The milestone's `_Test:_` has two halves. *"CRUD tests pass on SQLite and Postgres in CI"* is fully automated: every database test is parametrized over both engines, and CI fails if the PostgreSQL half is missing. *"In production, the sample questions are visible and the boot count increases across a redeploy"* is automated on every release by the deploy job's *Verify data* step (revision equals head, boots strictly higher), and on every PR by the `image` job (real container, PostgreSQL, restart → +1). Remaining once-before-acceptance procedures (outside device, defect PR, failing production migration, credential review) are in Complexity Tracking. Unit tests go in `tests/unit/`, database and HTTP tests in `tests/integration/`. No external service is called: CI's PostgreSQL is a local disposable container, and Neon is never reached by tests. |
| IV | Role-Based Access & Data Scoping (NON-NEGOTIABLE) | **DEVIATION (recorded in Complexity Tracking)** | Two literal rules cannot be met before roles exist (milestones 4–5): "authorization on every route and every service operation" and "a route without an explicit role requirement is a defect". The question service's `create`/`update`/`delete` carry no authorization, and the changed `GET /` has no explicit role requirement. Both are recorded as a deviation below, with the obligation on milestones 5 and 6 that ends it. Until then, the principle's intent is enforced in the strongest form available. The only data surface is the **anonymous, read-only** home page, which shows only question text; reference answers never reach the template (`QuestionPublic`). **No route accepts a write method at all**, asserted by `test_routes.py` over the whole route table (FR-018). The service has no caller besides tests. The obligation is written into [contracts/question-service.md](./contracts/question-service.md#conventions). |
| V | Secure Authentication & Secrets | **PASS** | The one new secret, the Neon connection string, lives only in Render's service environment (`sync: false` in `render.yaml`, value entered in the dashboard). It is not in GitHub, the repository or the image. Error messages about configuration never include the URL (`from None` suppresses SQLAlchemy's echoing parse error). The engine uses `hide_parameters=True`, and startup logs only the dialect name, revision and boot count. CI's PostgreSQL uses `trust` auth, so the workflows contain **no** password, not even a disposable one. Fork PRs still reach no secret (`checks.yml` gains only a service container). Verified by quickstart V10. |
| VI | Trustworthy LLM Evaluation | **N/A** | No LLM usage (milestone 10). The `reference_answer` field stored now is the future scoring input; it is kept out of public views from day one. |
| VII | Data Integrity & Migrations | **PASS (one justified engine-specific feature)** | All tables are SQLModel models in `app/models/`. Every schema change is an Alembic migration in `migrations/`, and there is **no `create_all()`** anywhere, including tests, which migrate with Alembic. The same code and migrations run on SQLite and PostgreSQL, proven by the both-engine suite, including a **drift test** (models = migrated schema) and a stairway test. Timestamps are UTC-aware on both engines via `UTCDateTime`. Migrations run automatically as part of deployment (entrypoint). The one PostgreSQL-specific feature, `pg_advisory_xact_lock` in `env.py`, is justified in Complexity Tracking. Competition windows and result protection have nothing to apply to yet (milestones 8–11); question deletion is a safe hard delete because nothing references questions. |
| — | Technology Stack table | **PASS** | Exactly the milestone-3 rows are introduced: SQLModel, Alembic, SQLite → PostgreSQL. Nothing from later rows is added. Python, FastAPI, Jinja2, Pico.css, uv, ruff, pytest, Docker, Render and GitHub Actions are unchanged. |
| — | Open stack decision: managed PostgreSQL offering | **RESOLVED** | **Neon, free plan, PostgreSQL 17, AWS Europe Central 1 (Frankfurt), direct endpoint**, chosen by the user over Render's free (30-day expiry) and paid (monthly cost) PostgreSQL. The expiry and data-retention question the spec asks this plan to record: Neon's free plan has **no expiry**; storage and compute allowances are far above need and are re-checked at bootstrap ([research D1](./research.md#d1--managed-production-postgresql-neon-free-plan)). This is a choice of *offering* within the stack's "PostgreSQL (production)" row, so no amendment is needed. |
| — | Application Layout | **PASS** | `core/`: configuration (`config.py`), engine and session (`db.py`), and migration-state helpers (`migrations.py`). `models/`: tables only. `schemas/`: input and view models. `services/`: all logic (question operations, boot counting, status). `routers/pages.py` stays a thin handler (call services, render, map a database error to the notice). Templates stay in `templates/pages/`. `migrations/` at the root is the constitution's mandated location. |
| — | Operational Constraints | **PASS** | One Docker image, configured only by environment variables. Migrations are applied as part of deployment (entrypoint). The database-down state renders a friendly page, and no stack trace reaches users. |
| — | Development Workflow gate 3 (PR gates) | **PASS except role-access tests (Principle IV deviation)** | CI is still green-or-blocked on the same two contexts. The new tables arrive with migrations. No route is added, but `GET /` is **changed**, and the gate asks changed routes for role-access tests. With no roles yet, the only access to test is anonymous. `test_home.py` checks that an anonymous visitor gets the page, and `test_routes.py` checks that no route accepts a write method. Per-role allowed/denied tests are part of the Principle IV deviation below. No secrets in the diff (V10). README updated in the same PR (FR-032, Workflow §5). |

**New runtime dependencies** (Principle II requires each to be justified):

| Dependency | Why it is needed now | Why it is the minimum |
|---|---|---|
| `sqlmodel` | The constitution mandates SQLModel for all tables from milestone 3. | Brings SQLAlchemy 2.0 and reuses the Pydantic already present through FastAPI; no separate ORM or validation library. |
| `alembic` | The constitution mandates Alembic migrations from milestone 3 (FR-007). | The only migration tool for SQLAlchemy; used from the CLI and read by the startup guard. |
| `psycopg[binary]` | Production is PostgreSQL, and SQLAlchemy needs a DB-API driver. | Sync driver matching the sync design. `binary` bundles `libpq`, so the slim image needs no `apt-get` layer. SQLite needs nothing extra. |

**New infrastructure dependencies**:

| Dependency | Where | Why it is the minimum |
|---|---|---|
| Neon free project | production database | The user's chosen offering: free, no expiry, same city as the service. |
| `postgres:17` service container | CI `quality` and `image` jobs | The disposable instance of the production engine that the spec's Dependencies require. Password-less, same major version as production. |

**Post-Phase 1 re-check**: **PASS with one recorded deviation**. No verdict changed after writing
[data-model.md](./data-model.md), the [contracts](./contracts/) and
[quickstart.md](./quickstart.md). The design stayed within the stack table and the layout. It
introduced exactly the three dependencies above, one engine-specific statement, the pre-auth
Principle IV deviation (both justified below), and no write route. Two design details strengthened principles rather than bending them:
`QuestionPublic` makes FR-022 structural rather than a template convention (IV, VI), and the
deploy job's data check automates a criterion milestone 2 would have left manual (III).

## Project Structure

### Documentation (this feature)

```text
specs/003-database-questions/
├── plan.md                      # This file (/speckit-plan command output)
├── spec.md                      # Feature specification (/speckit-specify)
├── research.md                  # Phase 0: D1…D14, decisions & rejected alternatives
├── data-model.md                # Phase 1: tables, schemas, revisions, seed content, configuration
├── quickstart.md                # Phase 1: Neon bootstrap, local run, validation V1…V10
├── contracts/
│   ├── http-routes.md           # Phase 1: GET / list + status line + unavailable state; no write routes
│   ├── question-service.md      # Phase 1: internal CRUD interface + behaviour matrix
│   ├── configuration.md         # Phase 1: DATABASE_URL resolution, Render guard, error messages
│   └── pipeline.md              # Phase 1: Dockerfile, render.yaml, checks.yml, deploy.yml deltas
├── checklists/
│   └── requirements.md          # Spec quality checklist
└── tasks.md                     # Phase 2 output (/speckit-tasks, NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml                      # CHANGED: + sqlmodel, alembic, psycopg[binary]
uv.lock                             # CHANGED: regenerated by `uv add`
alembic.ini                         # NEW: script_location, dated file_template, ruff post-write hooks; no URL
Dockerfile                          # CHANGED: copy alembic.ini + migrations/, writable /app/data, migrate-then-exec entrypoint
.dockerignore                       # CHANGED: ship migrations/; exclude data/, *.sqlite3, *.db
.gitignore                          # CHANGED: + data/
render.yaml                         # CHANGED: + DATABASE_URL (sync: false)
README.md                           # CHANGED: migrate command, env vars, PostgreSQL tests, adding a migration

.github/workflows/
├── checks.yml                      # CHANGED: postgres:17 service; TEST_POSTGRES_URL; image job runs on PostgreSQL + restart + refusal
├── ci.yml                          # unchanged
└── deploy.yml                      # CHANGED: uv sync, expected head, previous boots, verify data

scripts/
├── database_status.sh              # NEW: `boot-count <url>` / `verify <url> <revision> [<prev-boots>]`
├── render_deploy.sh                # unchanged
├── wait_for_release.sh             # unchanged
└── setup_branch_protection.sh      # unchanged (same required contexts)

migrations/                         # (had only .gitkeep)
├── env.py                          # NEW: URL from resolve_database_url; SQLModel.metadata; batch on SQLite; advisory lock on PG
├── script.py.mako                  # NEW: revision template (+ `import sqlmodel`)
└── versions/
    ├── YYYY_MM_DD_<rev>_create_questions_and_boot_counter.py   # NEW: tables + boot row (1, 0)
    └── YYYY_MM_DD_<rev>_seed_sample_questions.py               # NEW: SAMPLE_QUESTIONS via frozen sa.table

app/
├── main.py                         # CHANGED: lifespan (resolve URL → engine → head guard → record_boot → app.state.engine)
├── core/
│   ├── config.py                   # CHANGED: + resolve_database_url, DatabaseConfigError, default SQLite path
│   ├── db.py                       # NEW: create_db_engine, get_session dependency, UTCDateTime, utc_now, naming convention
│   ├── migrations.py               # NEW: alembic Config anchored to the project root, head_revision, current_revision, ensure_at_head
│   └── templates.py                # unchanged
├── models/
│   ├── __init__.py                 # NEW: imports every table so SQLModel.metadata is complete
│   ├── question.py                 # NEW: Question (table `questions`)
│   └── boot_counter.py             # NEW: BootCounter (table `boot_counter`)
├── schemas/
│   └── question.py                 # NEW: QuestionCreate, QuestionUpdate, QuestionPublic
├── services/
│   ├── questions.py                # NEW: create/get/list/update/delete + QuestionNotFound
│   └── database_status.py          # NEW: record_boot, read_database_status, DatabaseStatus
├── routers/
│   ├── pages.py                    # CHANGED: sync `home` with Session; list + status; SQLAlchemyError → notice
│   └── health.py                   # unchanged (no I/O)
├── templates/pages/home.html       # CHANGED: questions section, empty state, status line, unavailable notice
└── static/css/app.css              # CHANGED: .question-list (pre-line, wrap), .db-status, .data-unavailable

tests/
├── conftest.py                     # CHANGED: engine-parametrized database_url; template+clone; function-scoped client; CI guard
├── unit/
│   ├── test_config.py              # unchanged
│   ├── test_database_config.py     # NEW: resolution table, normalisation, guard, no-URL-in-message
│   └── test_question_schemas.py    # NEW: trimming, blank, limits (code points), at-least-one-field
└── integration/
    ├── test_home.py                # CHANGED: list/order/once, no answers/forms, escaping, empty, unavailable, status attrs, 500 items
    ├── test_health.py              # CHANGED: + 200 while the database is failing
    ├── test_question_service.py    # NEW: the behaviour matrix in contracts/question-service.md
    ├── test_boot_counter.py        # NEW: +1 per start, not per view, concurrent increments
    ├── test_migrations.py          # NEW: empty→head, head→head, stairway, single head, no drift, samples; concurrent upgrade (PG)
    ├── test_startup.py             # NEW: refuses when behind head / on Render without URL; boots once per startup
    └── test_routes.py              # NEW: every route's methods ⊆ {GET, HEAD}
```

**Structure Decision**: the constitution's *Application Layout* is followed as is. Four placements
are worth stating:

- **`app/core/migrations.py` separate from `db.py`.** Reading Alembic's head needs the
  `alembic.ini` location, anchored to the project root just as templates are anchored to the
  package (milestone 2 D14). It is used by startup, by the status service and by the tests; keeping
  it apart keeps `db.py` free of Alembic imports.
- **`UTCDateTime` in `app/core/db.py`, not in `models/`.** The constitution reserves `models/` for
  tables. A column type is database infrastructure that every model uses.
- **Seed data inside its migration, not in `app/`.** A migration must be a frozen snapshot, so it
  cannot import application constants that may change later. Tests read `SAMPLE_QUESTIONS` from
  the revision module through Alembic's `ScriptDirectory`, so there is still a single source of
  truth ([research D6](./research.md#d6--sample-questions-a-data-migration-not-startup-code)).
- **`scripts/database_status.sh` beside the other release scripts.** Like `wait_for_release.sh`,
  it is used by the pipeline and by a person with the same result. It reads only public HTML and
  needs no credential.

## Complexity Tracking

One deviation from Principle IV, which lasts only until roles exist, is recorded here. So are one
engine-specific feature and the residual manual verification. Governance requires all of them to
be visible.

| Deviation / residual risk | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| **Principle IV / Workflow gate 3**: the question service's `create_question`, `update_question` and `delete_question` enforce no authorization; the changed `GET /` has no explicit role requirement; and there are no per-role allowed/denied tests. **Ends when**: milestone 5 introduces the role dependencies and must give `GET /` (and `/healthz`) an explicit public-access declaration; milestone 6, the first real caller of the write operations, must put a teacher role check in front of every call, with allowed/denied tests. | Users arrive in milestone 4 and roles in milestone 5, so nothing exists to check against. FR-013 and the milestone's _Test:_ ("CRUD tests pass on SQLite and Postgres") require the write operations to exist and be tested now. Meanwhile no route can call them: `test_routes.py` fails the build if any route accepts a method other than `GET`/`HEAD`. `GET /` is anonymous and read-only by product design, and `QuestionPublic` keeps reference answers out of it. | A placeholder role parameter or authorization dependency would be a stub with nothing to check. If it allowed every call, it would give false assurance. If it denied every call, the operations could not be tested. Either way it is an abstraction with no present need (Principle II). Deferring the write operations to milestone 6 contradicts FR-013 and the ladder's milestone-3 test. |
| **Principle VII**: `pg_advisory_xact_lock` in `migrations/env.py`, a PostgreSQL-only statement, guarded by `dialect.name == "postgresql"`. | The spec's edge case "two instances start at the same time" can happen during a Render deploy overlap. Without serialisation, both entrypoints run `upgrade head` against the same revision, and the loser fails its deploy on `CREATE TABLE` or, with later data migrations, applies them twice. The transaction-scoped lock releases itself on commit, rollback or crash. | A lock row in a table does not work for the **first** migration, which is the one that would create the table. No lock at all leaves overlapping deploys to chance. SQLite needs no equivalent: it is local and single-process, and its database-level write lock already serialises writers. |
| **Principle VII / FR-010 on SQLite**: a failing migration can leave a local SQLite database partially migrated. | Alembic does not run SQLite DDL transactionally. FR-010 concerns the production publish, which is PostgreSQL, where the whole upgrade is one transaction. | Emulating transactional DDL on SQLite would mean snapshotting the file before every upgrade, which is complexity for a throw-away local database. Recovery is documented: fix the migration and re-run, or delete the file. |
| **Principle III**: SC-001 (outside device), SC-004 (defect PR blocked), SC-007 (failing production migration) and SC-010 (credential review) are once-before-acceptance procedures ([quickstart.md](./quickstart.md) V5, V3, V7, V10), not tests. | Each asserts something about the platform, the network or the whole repository and logs, not about application behaviour. SC-007 in particular needs a migration that fails **only in production**, because any migration that fails in CI cannot be merged. | Automating them would mean scheduled bots that break `main` or production on purpose (same reasoning as milestone 2). Two criteria that milestone 2 would have left manual are automated instead: SC-002 (boot count rises across a redeploy) runs on every release, and "migrations run in the packaged image" runs on every PR. |
| **Vendor split**: the production database is on Neon, outside the Render Blueprint, so `render.yaml` cannot link it and the connection string is entered by hand once. | The user chose Neon so that production data does not expire after 30 days, which Render's free database does. | Render PostgreSQL free expires mid-project. Render paid costs money every month. Moving later is a `render.yaml` change plus a one-off data copy, with no code change. |
