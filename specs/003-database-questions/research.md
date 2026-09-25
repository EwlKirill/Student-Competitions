# Research & Decisions: Database & First Entity — Questions (Milestone 3)

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](./plan.md)

Every unknown in the plan's Technical Context is resolved here. Each entry records the decision,
why it was made, and what was rejected. Platform facts are those documented by Render and Neon at
the time of writing; the ones that could drift (free-plan limits) are flagged for a re-check at
bootstrap time in [quickstart.md](./quickstart.md).

---

## D1 — Managed production PostgreSQL: Neon, free plan

**Decision**: production uses a **Neon** project on the **free plan**, region **AWS Europe
Central 1 (Frankfurt)**, **PostgreSQL 17**, reached through the project's **direct** (non-pooled)
connection string. The connection string is stored only as the Render service's `DATABASE_URL`
environment variable, entered once in the Render dashboard; `render.yaml` declares the key with
`sync: false` and no value. This closes the constitution's open stack decision "managed
PostgreSQL offering", which milestone 2 deferred to this milestone.

**Rationale**:

- **Persistence is the milestone's whole point**, and the project will run for months (milestones
  3–12). Neon's free plan has no expiry date. Render's free PostgreSQL expires 30 days after
  creation (followed by a grace period, then deletion). The production data would be gone before
  milestone 6.
- **Same region as the web service.** Render's service runs in `frankfurt` (milestone 2, D1);
  Neon's `aws-eu-central-1` is in the same city, so a query costs about a millisecond of network,
  well inside SC-005's 3 seconds.
- **Idle behaviour fits the web tier.** Neon suspends the compute after a few idle minutes and
  resumes on the next connection, typically in well under a second. The Render free instance
  already needs about a minute to spin up from idle, so the database never becomes the slow part.
  `pool_pre_ping` (D10) absorbs the connections Neon closes while suspended.
- **Free-plan capacity is far above the need.** The free plan includes 0.5 GB of storage per
  project and a monthly compute allowance. This milestone stores a few kilobytes; the whole product
  (questions, ~10-student competitions, scores) stays in megabytes. *Re-check the current limits
  on Neon's pricing page when creating the project.*
- **Direct, not pooled, endpoint.** One small service with one uvicorn worker needs a handful of
  connections, well under the direct endpoint's limit. The pooled endpoint (PgBouncer in
  transaction mode) adds nothing here and complicates session-level behaviour. The migration lock
  (D5) is transaction-scoped and would survive pooling, but psycopg's server-side prepared
  statements and future session state would not.
- **PostgreSQL 17** is chosen explicitly at project creation, and CI's disposable server uses the
  same major version (D12). The two are bumped together or not at all.

**Consequences accepted**:

| Property | Effect |
|---|---|
| A second vendor account (Neon) alongside Render | One extra bootstrap step (quickstart N1). The spec's Dependencies allow a database "on (or alongside) the hosting platform". |
| The connection string is entered by hand in Render, not linked by the Blueprint | `render.yaml` can link only Render-hosted databases with `fromDatabase`. `sync: false` documents the key in code and keeps the value out of it (FR-003, FR-032). |
| Forgetting to set `DATABASE_URL` before the milestone's first release | The release fails loudly and the previous version keeps serving (D3, FR-004). This is the designed failure path, not a data risk. |
| Point-in-time restore window on the free plan is short | Backups and restore are out of scope for this milestone (spec *Out of Scope*). |

**Alternatives considered**:

- **Render PostgreSQL, free.** Linked automatically by the Blueprint with a single vendor.
  Rejected because of the 30-day expiry: the database would have to be recreated (losing all data)
  or upgraded partway through the project. That makes "data survives redeploys" true for a few
  weeks only.
- **Render PostgreSQL, paid (Basic-256mb, about $6/month).** No expiry and a single vendor.
  Rejected by the user in favour of a free option. If it is adopted later, the only changes are a
  `databases:` entry and a `fromDatabase` reference in `render.yaml`, plus a one-off data copy. No
  application code changes.
- **Supabase free.** Pauses projects after a week of inactivity, and resuming is a manual
  dashboard action. An unattended project would fail its next deploy.
- **A SQLite file on a Render persistent disk.** Disks are not available on free instances, and
  the constitution fixes PostgreSQL for production.

**Evidence**: Render docs: *Free instance types* (free PostgreSQL expiry; no persistent disks),
*Blueprint YAML reference* (`sync: false`, `fromDatabase`). Neon docs: *Plans* (free-plan
storage, no expiry), *Regions* (`aws-eu-central-1`), *Scale to zero*, *Connection pooling*
(direct vs. pooled endpoints).

---

## D2 — ORM, migrations and driver: SQLModel (sync) + Alembic + psycopg 3

**Decision**: three new runtime dependencies, all scheduled by the constitution for milestone 3:

| Package | Pinned by `uv.lock` at plan time | Role |
|---|---|---|
| `sqlmodel` | 0.0.47 (brings SQLAlchemy 2.0.54) | Table models in `app/models/` and input/view schemas in `app/schemas/` |
| `alembic` | 1.20.0 | Versioned migrations in `migrations/` |
| `psycopg[binary]` | 3.3.6 | PostgreSQL driver; the `binary` extra bundles `libpq`, so the slim runtime image needs no system packages |

SQLite needs no driver: it uses Python's built-in `sqlite3`.

All database access is **synchronous**: a sync engine, sync `Session`, and plain `def` route
handlers (which FastAPI runs in its threadpool, so the event loop is never blocked).

**Rationale**:

- The constitution names SQLModel and Alembic, so the only real choice is the driver and the
  sync/async question.
- **psycopg 3 over psycopg2.** psycopg 3 is the maintained line, ships Python 3.13 wheels with
  `libpq` included, and is what SQLAlchemy 2.0 documents as the modern PostgreSQL driver. Its cost
  is a URL prefix: SQLAlchemy reads a bare `postgresql://` as psycopg2, so D3 normalises the
  scheme to `postgresql+psycopg://`.
- **Sync over async.** SQLModel's documented, tested path is synchronous. The workload is tiny
  (tens of students). Async would add `asyncpg` or `psycopg`'s async mode, `aiosqlite`, an async
  Alembic `env.py` and async test fixtures, with no present need (Principle II, YAGNI).
- **No `pydantic-settings` yet.** Milestone 2 (D6) expected a typed settings object to become
  worthwhile here. It still is not: the new configuration is one variable plus one guard (D3), and
  a pure function over `os.environ` covers it and is trivially unit-tested. Milestone 4 (session
  secret, mail credentials) is the next point to reconsider.

**Alternatives considered**: `asyncpg` with an async engine (rejected above); psycopg2-binary
(rejected: legacy line, and it would only save the URL rewrite); raw SQLAlchemy Core without
SQLModel (rejected: the constitution fixes SQLModel).

---

## D3 — Database configuration: `DATABASE_URL`, a local default, and a production guard

**Decision**: one pure function, `resolve_database_url(environ)` in `app/core/config.py`, is the
only place the database location is decided. Both the application's startup and Alembic's
`env.py` call it, so the two can never disagree:

1. **`DATABASE_URL` set and non-empty.** The URL is parsed, then checked for a supported
   scheme (`sqlite`, `postgres`, `postgresql`, `postgresql+psycopg`). `postgres://` and
   `postgresql://` are rewritten to `postgresql+psycopg://`, keeping the rest of the URL
   (credentials, host, `?sslmode=require&channel_binding=require`) unchanged.
2. **Unset, and `RENDER` is set** (Render sets `RENDER=true` on every service automatically).
   The function raises `DatabaseConfigError`: *"DATABASE_URL is required when running on Render;
   refusing to fall back to a local SQLite file."* (FR-004).
3. **Unset, not on Render.** The default is a SQLite file at
   `<project root>/data/student_competitions.sqlite3`, with the `data/` directory created on
   demand (FR-002). The path is anchored to the package, not the working directory, following
   milestone 2 D14. `data/` is git-ignored and docker-ignored.

Error messages **never include the URL**. SQLAlchemy's `make_url` echoes the input string in its
own parse error, so that error is caught and re-raised as `DatabaseConfigError(...) from None`
with a message that names only the problem, for example "unsupported scheme 'mysql'" (FR-004,
FR-032).

**Rationale**:

- **Keying the guard on `RENDER` rather than a new `APP_ENV` variable.** The failure FR-004
  guards against is someone forgetting configuration. A guard that is itself a variable someone
  must remember to set would fail in exactly that case. `RENDER` is set by the platform and cannot
  be forgotten. If the project moves to Railway or Fly.io, the guard gains that platform's
  equivalent variable; this is recorded in [contracts/configuration.md](./contracts/configuration.md).
- **The container keeps working with no configuration locally.** Milestone 2 promised that
  `docker run -p 8000:8000 student-competitions` just works. The image creates `/app/data` owned
  by the non-root user, so the default SQLite file is writable there. It is throw-away by design,
  because the guard makes that path unreachable on Render.
- **Relative-to-package default.** A developer starting the app from a subdirectory must not get a
  second, empty database. That is exactly the bug D14 fixed for templates.

**Alternatives considered**: a required `DATABASE_URL` everywhere (rejected: breaks FR-002 and
SC-008's "no database configuration"); `APP_ENV=production` (rejected above); an in-memory SQLite
default (rejected: fails FR-001, since the data would not survive a restart).

---

## D4 — Where migrations run: the container entrypoint, then a startup guard

**Decision**:

- **In the image**, the entrypoint becomes
  `sh -c "alembic upgrade head && exec uvicorn app.main:app --host … --port …"`. Migrations run
  in a short-lived process **before** uvicorn binds the port. If they fail, the command exits
  non-zero, uvicorn never starts, the new instance never passes `/healthz`, Render fails the
  deploy, and the previous instance keeps serving (FR-009, FR-010). `alembic.ini` and
  `migrations/` are copied into the image; `migrations/` is removed from `.dockerignore`.
- **Locally**, one documented command, `uv run alembic upgrade head`, brings the developer's
  database to head (FR-011). A developer runs it after cloning and after pulling a new migration.
- **Everywhere**, the application's startup (FastAPI `lifespan`) compares the database's current
  revision with the head of `migrations/`. It **refuses to start** if they differ, with an
  actionable message: *"Database is at revision X but the code expects Y — run
  `uv run alembic upgrade head`."* The application never serves against a schema it was not
  written for.

**Rationale**:

- **Render's pre-deploy command, the platform's designed place for migrations, is not available
  on the free instance type.** The entrypoint is the equivalent that is available: it runs once per
  new instance, before traffic, and its failure prevents the switch-over. Milestone 2's plan
  anticipated exactly this one-line change.
- **Migrations as a separate process, not inside the app's `lifespan`.** A process that only
  migrates can exit cleanly, keeps Alembic's logging configuration out of uvicorn's, and does not
  couple "serve requests" to "alter the schema". The guard keeps the useful half of the in-app
  approach (never serve a mismatched schema) without the app ever changing its own structure
  (FR-007).
- **Why the guard is worth its few lines.** Without it, a developer who forgets the migrate
  command sees `no such table: questions` on the first page view. With it, startup fails with the
  exact command to run. In production it is a second, independent check that the release and the
  schema agree.

**Rule for every later migration (recorded here because the entrypoint makes it binding)**: during
a successful deploy, the **new** schema is committed while the **old** release may still be
serving for a few seconds. Migrations must therefore be backward compatible with the previous
release (expand, then contract in a later release). This milestone's migrations only create
tables and insert rows, which the milestone 2 release never reads, so they satisfy the rule
trivially.

**Alternatives considered**:

- **Render `preDeployCommand`**: rejected, not available on free instances. If the plan is ever
  upgraded, moving `alembic upgrade head` there is a two-line change: add it to `render.yaml` and
  drop it from the CMD.
- **`alembic upgrade head` inside `lifespan` in every environment**: rejected for the reasons
  above. It would also run migrations on every `--reload` and in every worker if workers were ever
  added.
- **A migration step in the GitHub Actions deploy job, connecting to Neon from the runner**:
  rejected. It would put the production credential into GitHub. It would also migrate before
  Render has even built the image, so a build failure would leave the new schema live under the
  old code with no release to match it.
- **`SQLModel.metadata.create_all()`**: forbidden by Principle VII.

---

## D5 — Migration atomicity and concurrent starts

**Decision**:

- **Atomicity (FR-010).** Alembic's default on PostgreSQL runs the whole `upgrade head`, all
  pending revisions, in **one transaction** (`transaction_per_migration` stays `False`). PostgreSQL
  has transactional DDL, so a failure anywhere rolls back every statement and the `alembic_version`
  update together. The database stays at its previous revision.
- **Concurrency (edge case "two instances start at the same time").** On PostgreSQL, `env.py`
  takes a transaction-scoped advisory lock, `SELECT pg_advisory_xact_lock(<fixed 64-bit key>)`,
  inside the migration transaction **before** Alembic reads the current revision. A second
  instance blocks until the first commits, then reads the new head and has nothing to do. The lock
  is released automatically at commit or rollback, including when the process dies.
- **SQLite.** Alembic does not run SQLite migrations transactionally, so a failing local migration
  can leave a partial schema. The recovery is to fix the migration and re-run it, or delete the
  local file. This is acceptable because SQLite is only ever local and single-process; FR-010 is
  about publishing, which is PostgreSQL. `env.py` sets `render_as_batch=True` on SQLite so later
  `ALTER` migrations work there.

**Rationale**: the advisory lock is the **one PostgreSQL-specific feature** this milestone uses,
and Principle VII requires justifying it. It is the standard, cheap way to serialise schema
changes. The only alternative that works on both engines, a lock row in a table, needs a table
that exists before the first migration. The lock is guarded by `dialect.name == "postgresql"`, and
SQLite needs no equivalent because its single writer serialises access already. Recorded in the
plan's Complexity Tracking.

**Alternatives considered**: no lock (rejected: two overlapping first starts would both try
`CREATE TABLE`, and the loser fails its deploy); a session-level `pg_advisory_lock` (rejected: it
must be released explicitly, and a crash leaves it held until the connection dies);
`transaction_per_migration=True` (rejected: a failure in revision 2 would leave revision 1
committed, so the "previous consistent version" would depend on where it failed).

---

## D6 — Sample questions: a data migration, not startup code

**Decision**: the sample questions are inserted by their **own Alembic revision**
(`seed_sample_questions`), after the revision that creates the tables. The revision carries its
data as a module-level constant (`SAMPLE_QUESTIONS`) and inserts it with `op.bulk_insert` against
a **frozen** `sa.table(...)` definition, not the live `Question` model.

**Rationale**:

- **"Exactly once per database" comes free (FR-019, FR-020).** Alembic records the revision as
  applied, so it can never run again against that database, whether on a restart, a redeploy or a
  re-applied `upgrade head`. With D5's lock, two concurrent first starts cannot both run it either.
- **No "insert if the table is empty" logic at startup.** That approach races between concurrent
  starts, and it would **re-seed** a database whose questions a teacher deliberately deleted in
  milestone 6.
- **A frozen table definition** keeps the migration valid forever, even after the `Question` model
  gains columns in milestones 6 and 8.
- **Tests read the same constant** through Alembic's `ScriptDirectory`
  (`script.get_revision(rev).module.SAMPLE_QUESTIONS`), so "the sample questions" has a single
  source of truth and the tests never keep a copy that could drift.

**Alternatives considered**: seeding in `lifespan` (rejected above); a CLI seed command (rejected:
a manual step, which FR-019 forbids); fixtures loaded from a JSON file (rejected: a second file
format for five rows).

---

## D7 — Boot counter: one row, one atomic `UPDATE` per start

**Decision**: a table `boot_counter` holds exactly one row (`id = 1`, enforced by
`CHECK (id = 1)`), created with `boots = 0` by the first migration. On every application start,
`lifespan` runs, in its own short transaction:

```sql
UPDATE boot_counter SET boots = boots + 1 WHERE id = 1
```

and then checks that exactly one row was updated (otherwise startup fails). The home page reads
`boots` on each request and never writes it (FR-028).

**Rationale**:

- **No lost increments.** `boots = boots + 1` is evaluated by the database under a row lock
  (PostgreSQL) or the database write lock (SQLite). Two overlapping starts always yield `+2`. A
  read-modify-write in Python could lose one. This is proven by a concurrent test on both engines.
- **"Start" means the application process start** (spec *Assumptions*): one uvicorn worker, one
  `lifespan` startup, one increment. The `alembic upgrade head` process in the entrypoint is not
  the application and does not count. A local `--reload` restarts the application and does count,
  which is correct.
- **A failed increment is a failed start.** If the database is unreachable at startup, the
  exception escapes `lifespan`, uvicorn exits, and the release fails (spec edge case "Database
  unreachable at startup").

**Alternatives considered**: an append-only `boots` table with one row per start (rejected:
unbounded growth for no present need, although it would record timestamps); counting in
`/healthz` (rejected: FR-029 keeps `/healthz` free of I/O).

---

## D8 — Timestamps: one UTC-aware column type for both engines

**Decision**: a SQLAlchemy `TypeDecorator`, `UTCDateTime` in `app/core/db.py`, wraps
`DateTime(timezone=True)`:

- **bind**: rejects naive datetimes (a programming error), converts aware ones to UTC;
- **result**: returns an aware UTC datetime on both engines. SQLite stores no offset, so a naive
  value read back is tagged `UTC`; PostgreSQL's `timestamptz` is converted to UTC.

All timestamps come from one helper, `utc_now()`, so tests can control the clock.

**Rationale**: FR-006 and Principle VII require timezone-aware UTC. PostgreSQL does that natively.
SQLite silently returns naive datetimes, which is precisely the "works locally, differs in
production" bug US4 exists to catch. One type makes both engines return the same value, and a
round-trip test on both engines proves it.

**Alternatives considered**: storing epoch integers (rejected: unreadable in the Neon console, and
it pushes conversion into every query); relying on `timezone=True` alone (rejected: it does
nothing on SQLite).

---

## D9 — Question operations: schemas at the boundary, functions in a service

**Decision**:

- **Input validation** lives in `app/schemas/question.py`: `QuestionCreate` (`text`,
  `reference_answer`, both required) and `QuestionUpdate` (both optional; at least one must be
  given). Each field **strips surrounding whitespace**, then must be non-empty and within its
  limit: 1,000 characters for `text`, 5,000 for `reference_answer`, counted in Unicode code points
  after stripping. Internal line breaks and all other characters are stored exactly (FR-014,
  FR-017). Invalid input raises Pydantic's `ValidationError` before any database access, so
  nothing is stored or changed.
- **Operations** are plain functions in `app/services/questions.py` that take a `Session`:
  `create_question`, `get_question`, `list_questions`, `update_question`, `delete_question`. A
  missing identifier raises `QuestionNotFound` (a `LookupError` subclass) from `get`, `update` and
  `delete` (FR-015). `update_question` sets `updated_at = utc_now()`. Listing orders by
  `created_at, id` (FR-016).
- **A read-only view**, `QuestionPublic` (`id`, `text`), is what the home page receives. Reference
  answers never reach the template (FR-022), so a later template edit cannot leak them by
  accident.
- **Column lengths** are also declared in the schema (`VARCHAR(1000)`, `VARCHAR(5000)`).
  PostgreSQL enforces them as a backstop; SQLite ignores them, which is why the schema, not the
  column, is the validation gate.

**Rationale**: this is the shape milestone 6's router will use without change: parse the form into
`QuestionCreate`, render `ValidationError` messages, call the service, map `QuestionNotFound` to
404. Functions rather than a repository class: no second implementation exists or is planned, so a
class would be an abstraction without a present need (Principle II). The interface is written down
in [contracts/question-service.md](./contracts/question-service.md).

**Stripping surrounding whitespace** is how FR-014's "non-blank after trimming" and FR-017's
"preserve content exactly" fit together. The stored value is the trimmed text, and everything
inside it (line breaks, Cyrillic, `<b>`) round-trips byte for byte.

**Alternatives considered**: validating on the table model (rejected: SQLModel skips validation
for `table=True` models); `Optional` return for "not found" (rejected: FR-015 asks for an
explicit outcome, and a `None` is easy to ignore); UUID primary keys (rejected: integers give a
natural tie-break for ordering and readable ids, and access control, not unguessability, protects
the milestone 6 routes).

---

## D10 — Home page: rendering the list, and surviving a database blip

**Decision**:

- `GET /` becomes a sync `def` handler with a `Session` dependency. It calls
  `list_questions` and `read_database_status` and renders the milestone 1 hero, then a
  **"Sample questions"** section, then the status line.
- Question text is rendered through Jinja2's default autoescaping (FR-024). CSS gives it
  `white-space: pre-line` (line breaks shown) and `overflow-wrap: anywhere` (long text wraps on a
  phone). No `|safe` anywhere.
- The status line carries machine-readable attributes
  (`data-engine`, `data-revision`, `data-boots`) next to its human text, so the deploy job and the
  CI smoke test read it without scraping prose (D13).
- **Database failure at request time (FR-026).** The handler catches `SQLAlchemyError` around the
  two reads, logs it (type and message only, never the URL), and renders the same page with a
  friendly *"Question data is temporarily unavailable. Please try again in a moment."* in place of
  both the list and the status line. The response is still `200`, and `/healthz` is untouched.
- **Engine settings.** `pool_pre_ping=True` (Neon closes idle connections when it suspends);
  PostgreSQL `connect_timeout=5` so an unreachable database fails the page within seconds instead
  of hanging; SQLite `check_same_thread=False` because FastAPI's threadpool may use a different
  thread than the one that opened the connection; `hide_parameters=True` so bound values never
  appear in error logs.

**Rationale**: a `200` with a notice is FR-026's "page still renders". A `503` would be a better
signal for machines, but the page's audience is people, and the machine signal already exists
(the release checks, D13). Catching at the handler rather than a global exception handler keeps
the hero and layout rendering normally, which is what the spec's edge case describes.

**Alternatives considered**: HTMX lazy-loading the list as a partial (rejected: no interactivity
is needed, and it would add a second request and a JSON-free-but-still-extra endpoint for no
present need); caching the list in memory (rejected: SC-005's 3 seconds is met by three small
queries, and caching would hide the persistence the page exists to prove).

---

## D11 — Liveness vs. readiness: no new endpoint

**Decision**: `/healthz` stays exactly as milestone 2 defined it, with no I/O and the same three
keys (FR-029). **No readiness endpoint is added.**

**Rationale**: readiness is already enforced by startup order. Uvicorn binds the port only after
`lifespan` startup completes, and startup completes only after the migrations ran (entrypoint),
the schema matched head, and the boot increment succeeded. So an instance that answers `/healthz`
at all has already proven the database was reachable and current when it started. Render routes
traffic only after `/healthz` passes, and that is the readiness gate. After start, a database blip
must **not** make `/healthz` fail, or Render would restart a healthy process in a loop (FR-029).
A separate readiness route would have no consumer: Render's free web service has a single
health-check path.

**Alternatives considered**: a database ping inside `/healthz` (rejected: FR-029, and the 5-second
health-check budget); `/readyz` (rejected: no consumer).

---

## D12 — Tests on both engines: one parametrized fixture, template-and-clone isolation

**Decision**:

- **Engine parametrization.** A `database_url` fixture in `tests/conftest.py` is parametrized over
  `["sqlite", "postgresql"]`. Every test that touches the database, including every HTTP test
  (the app cannot start without one), therefore runs once per engine, and pytest's ids
  (`[sqlite]`, `[postgresql]`) make the split visible in the log (FR-030, SC-003).
- **Where PostgreSQL comes from.** Tests read `TEST_POSTGRES_URL`, a server URL whose role can
  `CREATE DATABASE`. It is never `DATABASE_URL`, so a test can never point at a developer's data
  or at production (FR-031). When the variable is absent, the `postgresql` cases are **skipped**
  locally with a reason telling the developer how to run them. When `CI=true` (set by GitHub
  Actions), a missing `TEST_POSTGRES_URL` **fails the session** at start, so CI cannot pass by
  skipping half the matrix.
- **Isolation: migrate once, clone per test.** Once per session and per engine, a fresh database
  is created and migrated to head **with Alembic** (so every run also exercises the migrations).
  Each test then gets its own clone of it:
  - SQLite: a file copy into `tmp_path` (about a millisecond);
  - PostgreSQL: `CREATE DATABASE sc_test_<run>_<n> TEMPLATE sc_test_<run>_template`, dropped with
    `DROP DATABASE … WITH (FORCE)` afterwards. Names carry a random per-run token, so parallel or
    repeated runs never collide, and the template itself is dropped at the end.
  Each test starts at exactly the state the migrations produce (sample questions present,
  `boots = 0`) and leaves nothing behind.
- **The application under test** gets its database the same way it does in production: the
  `client` fixture sets `DATABASE_URL` to the clone (via `monkeypatch`) before entering
  `TestClient(app)`, so `lifespan` resolves, guards, and increments exactly as it would on Render.
  The fixture becomes function-scoped.
- **CI's PostgreSQL** is a `postgres:17` service container on the `quality` job with
  `POSTGRES_HOST_AUTH_METHOD=trust`. Because there is **no password at all**, no credential
  appears in the workflow file, not even a throw-away one (SC-010).

**Rationale**: running the same test bodies on both engines is what FR-030 and US4 ask for, and
parametrizing one fixture guarantees "100% of these tests run on both engines" by construction
rather than by discipline. Clone-per-test is faster than migrating per test and simpler than
SAVEPOINT-based rollback. That rollback approach needs the pysqlite transaction workarounds, and
it could not isolate the application's own `lifespan` writes (the boot counter).

**Tests that are PostgreSQL-only, and why**: the concurrent-`upgrade` test (D5). The advisory lock
is PostgreSQL-only by design, and concurrent migration of a local SQLite file is not a supported
scenario. The concurrent **boot-increment** test runs on both engines.

**Alternatives considered**: `testcontainers` (rejected: a new dev dependency and a Docker
requirement for every local test run, when a URL variable does the job); a separate CI job per
engine (rejected: it would add a required status context and a branch-protection change for no
gain in signal); SAVEPOINT rollback per test (rejected above).

---

## D13 — Pipeline: the image is smoke-tested against PostgreSQL, and every release checks the data

**Decision**:

- **`checks.yml` → `quality`**: adds the `postgres:17` service and
  `TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres`; otherwise unchanged (ruff
  check, ruff format --check, pytest). The step now runs both engines.
- **`checks.yml` → `image`**: adds the same service, and runs the built container with
  `--network host` and `DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres`, the plain
  `postgresql://` form Neon hands out, so URL normalisation is exercised in the real image. The
  smoke test additionally asserts that `/` shows a sample question, `data-engine="postgresql"` and
  `data-boots="1"`. It then **restarts the container** and asserts `data-boots="2"`, which is the
  persistence proof (US2) run on every pull request. It also runs the image once with `RENDER=true`
  and no `DATABASE_URL`, and asserts a non-zero exit with the refusal message and no fallback
  (FR-004).
- **`deploy.yml` → `deploy`**: before triggering the release it reads the public page's
  `data-boots` (best effort: empty if the live release predates this milestone or is down). After
  `wait_for_release.sh` confirms the commit, a new `scripts/database_status.sh verify` step
  asserts that the public page shows `data-revision` equal to `alembic heads` for this commit
  (FR-009, US2 scenario 5), that the unavailable notice is **not** shown, and, when a previous
  count was read, that `data-boots` is **strictly higher** (SC-002, on every release).
- **Required status contexts are unchanged** (`checks / quality`, `checks / image`), so
  `scripts/setup_branch_protection.sh` needs no edit.

**Rationale**: the image job is where "the same code runs on PostgreSQL" is proven for the
**packaged** application, including `psycopg`'s bundled `libpq`, the entrypoint's migration step
and the non-root user's file permissions. The deploy-side check turns SC-002, otherwise a manual
once-only observation, into an assertion made on every release, at the cost of two `curl`s.
Reading `alembic heads` needs `uv sync` in the deploy job; `setup-uv`'s cache keeps that to
seconds. Time budget: the PostgreSQL service adds about 10–20 s of startup per job, well inside
SC-009's 10 minutes.

**Alternatives considered**: comparing boot counts through a JSON endpoint (rejected: `/healthz`
is fixed at three keys with no I/O, and a new JSON endpoint has no other consumer); running
migrations from the deploy job (rejected in D4).

---

## D14 — Migration housekeeping: naming, a single head, and drift detection

**Decision**:

- `alembic.ini` at the repository root, `script_location = %(here)s/migrations`, **no URL**
  (D3 supplies it), and
  `file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s` so files sort by date.
  Revision ids stay Alembic's random 12-hex default, and that id is what the status line shows.
- `post_write_hooks` run `ruff format` and `ruff check --fix` on generated revisions, so an
  autogenerated file never fails CI on style.
- `script.py.mako` imports `sqlmodel` (autogenerate may emit `sqlmodel.sql.sqltypes.AutoString`).
  Models also declare explicit SQLAlchemy types, so this is a safety net rather than a
  dependency.
- `SQLModel.metadata` uses a **naming convention** for indexes and constraints, so constraint
  names are identical on both engines and later SQLite batch migrations can find them.
- Two tests guard the migration history on both engines:
  - **single head**: `ScriptDirectory.get_heads()` has exactly one entry, so two branches that each
    add a migration cannot both merge unnoticed;
  - **no drift**: after `upgrade head`, Alembic's `compare_metadata(migrated database,
    SQLModel.metadata)` is empty, so a model change without a migration fails CI (FR-007).
- Each revision implements `downgrade()`, and a **stairway test** (`upgrade head → downgrade base
  → upgrade head`) runs on both engines. Downgrades are a local-development convenience only.
  Production rollback relies on atomic forward migrations (spec *Out of Scope*).

**Rationale**: these are the cheap guards that keep the migration history trustworthy for the nine
milestones that will add to it. Each one turns a class of mistake into a red CI check rather
than a failed production deploy.

---

## Summary of resolved unknowns

| Technical Context item | Resolved by |
|---|---|
| Managed PostgreSQL offering (open constitution decision) | D1: Neon free, Frankfurt, PG 17, direct endpoint |
| Driver, sync vs. async, settings library | D2 |
| How the database location is configured; FR-004 guard | D3 |
| When and where migrations run; FR-009/FR-010/FR-011 | D4, D5 |
| Concurrent starts (migrations, seeding, boot count) | D5, D6, D7 |
| Seeding mechanism (FR-019/FR-020) | D6 |
| UTC timestamps on SQLite (FR-006) | D8 |
| Validation rules, service interface, not-found (FR-012…FR-017) | D9 |
| Home page rendering, escaping, DB-down behaviour (FR-021…FR-026) | D10 |
| Readiness signal (spec *Assumptions*) | D11 |
| Tests on both engines, isolation (FR-030, FR-031) | D12 |
| CI and release verification (SC-002, SC-009) | D13 |
| Migration history hygiene (FR-007, FR-008) | D14 |
