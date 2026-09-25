---

description: "Task list for Database & First Entity — Questions (Milestone 3)"
---

# Tasks: Database & First Entity — Questions (Milestone 3)

**Input**: Design documents from `/specs/003-database-questions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle III is non-negotiable, and [plan.md](./plan.md) names
the test modules: `tests/unit/test_database_config.py`, `tests/unit/test_question_schemas.py`,
`tests/integration/test_question_service.py`, `test_migrations.py`, `test_boot_counter.py`,
`test_startup.py`, `test_routes.py`, plus extensions to `test_home.py` and `test_health.py`. Every
database-touching test runs on **both** engines (`[sqlite]` and `[postgresql]`) through one
parametrized fixture. Four success criteria (SC-001, SC-004, SC-007, SC-010) are verified by a
once-before-acceptance **manual procedure** rather than by pytest (see the plan's *Complexity
Tracking*). Those tasks are marked **[MANUAL]**.

**Organization**: Tasks are grouped by user story so each can be implemented and validated
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- **[MANUAL]**: A human procedure or a platform-console action; not automatable at this milestone
- Include exact file paths in descriptions

## Path Conventions

Single server-rendered web application, repository root: `app/` (application), `migrations/`
(Alembic), `tests/` (suite), `scripts/` (release helpers), `.github/workflows/` (pipeline), and
`alembic.ini` / `Dockerfile` / `.dockerignore` / `render.yaml` at the root. See the plan's
*Project Structure* for every new and changed file.

**Running the PostgreSQL half locally** (needed by every "run the suite" task below):

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
export TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the milestone 2 baseline, add the three runtime dependencies, and lay down
the Alembic scaffolding

- [X] T001 Confirm the milestone 2 baseline is green from the repository root: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`. All four must pass before any change is made
- [X] T002 Add the three runtime dependencies with `uv add sqlmodel alembic "psycopg[binary]"`, which updates `pyproject.toml` and regenerates `uv.lock`. Confirm the lock resolves to the versions recorded in [research D2](./research.md#d2--orm-migrations-and-driver-sqlmodel-sync--alembic--psycopg-3) (`sqlmodel` 0.0.47 with SQLAlchemy 2.0.54, `alembic` 1.20.0, `psycopg` 3.3.6) or record any newer patch in the pull request. **No** dev dependency is added (no `testcontainers`, no `pydantic-settings`)
- [X] T003 [P] Add `data/` to `.gitignore`, and in `.dockerignore` **remove** the `migrations/` exclusion and add `data/`, `*.sqlite3` and `*.db`, so a developer's local database never enters the repository or an image ([contracts/pipeline.md](./contracts/pipeline.md#container-dockerfile-dockerignore))
- [X] T004 [P] Create `alembic.ini` at the repository root per [research D14](./research.md#d14--migration-housekeeping-naming-a-single-head-and-drift-detection): `script_location = %(here)s/migrations`; `file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s`; **no `sqlalchemy.url`** (the URL comes from `resolve_database_url`, T009); `[post_write_hooks]` running `ruff format REVISION_SCRIPT_FILENAME` and then `ruff check --fix REVISION_SCRIPT_FILENAME` (`type = exec`, `executable = ruff`), so generated revisions never fail CI on style; and the standard `[loggers]`/`[handlers]`/`[formatters]` sections
- [X] T005 [P] Create `migrations/script.py.mako`, Alembic's default revision template plus `import sqlmodel` (autogenerate may emit `sqlmodel.sql.sqltypes.AutoString`), and delete `migrations/.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The database layer every user story rides on: the URL resolution and its production
guard, the engine and the UTC column type, both table models, the first migration, the
"database is at head" startup guard, the both-engine test fixtures, CI's PostgreSQL service and
the migrate-then-serve container entrypoint.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Once `lifespan`
requires a migrated database (T017), the app, the tests, CI and the image all break until the
rest of this phase is in place, so finish it as a unit.

### Tests (write first, confirm they FAIL)

- [X] T006 [P] Write `tests/unit/test_database_config.py` covering every row of *Outputs* and *Errors* in [contracts/configuration.md](./contracts/configuration.md), calling `resolve_database_url(environ)` with an explicit dict (never `os.environ`): `sqlite:///…` returned unchanged; `postgres://` and `postgresql://` rewritten to `postgresql+psycopg://` with user, password, host, port, database and `?sslmode=require&channel_binding=require` preserved exactly; `postgresql+psycopg://` unchanged; unset **and** empty-string `DATABASE_URL` without `RENDER` → `sqlite:///<project root>/data/student_competitions.sqlite3`, where `<project root>` is the parent of the `app` package (not the working directory: `monkeypatch.chdir(tmp_path)` and assert the same result); `DATABASE_URL` unset or empty with `RENDER=true` **and** with `RENDER=1` → `DatabaseConfigError` whose message contains `DATABASE_URL is required`; an unparseable URL → `DatabaseConfigError`; `mysql://…` and `sqlite+aiosqlite://…` → `DatabaseConfigError` naming the scheme only. For a URL with the recognisable password `s3cr3t-pa55` and host `ep-secret-host.example`, assert that neither string appears in `str(exc)` or `repr(exc)`, and that `exc.__cause__ is None` and `exc.__suppress_context__ is True` (`raise … from None`). Assert `DatabaseConfigError` subclasses `RuntimeError`
- [X] T007 Rewrite `tests/conftest.py` per [research D12](./research.md#d12--tests-on-both-engines-one-parametrized-fixture-template-and-clone-isolation):
  - an **autouse** fixture that `monkeypatch.delenv`s `DATABASE_URL` and `RENDER` (`raising=False`), so a developer's shell can never point a test at real data (FR-031);
  - a `pytest_sessionstart` hook that calls `pytest.exit(..., returncode=1)` with a clear message when `CI=true` and `TEST_POSTGRES_URL` is unset, so CI cannot go green by skipping half the matrix;
  - a random per-run token (e.g. `secrets.token_hex(4)`) used in every PostgreSQL database name;
  - a session-scoped **template** per engine, migrated to head once with `alembic.command.upgrade(alembic_config(), "head")` while `DATABASE_URL` points at it (use `pytest.MonkeyPatch.context()` in session scope). SQLite: a file under `tmp_path_factory`. PostgreSQL: `CREATE DATABASE sc_test_<run>_template` on an `AUTOCOMMIT` connection to `TEST_POSTGRES_URL`, dropped at session end with `DROP DATABASE … WITH (FORCE)`;
  - a `database_url` fixture, **parametrized over `["sqlite", "postgresql"]`** with those ids, that yields a per-test clone: SQLite, `shutil.copy` of the template into `tmp_path`; PostgreSQL, `CREATE DATABASE sc_test_<run>_<n> TEMPLATE sc_test_<run>_template`, dropped `WITH (FORCE)` afterwards. The `postgresql` case calls `pytest.skip("set TEST_POSTGRES_URL to run the PostgreSQL cases (see README)")` when the variable is unset. The yielded URL is in the normalised `postgresql+psycopg://` form;
  - an `empty_database_url` fixture, parametrized the same way, yielding a database with **no** migrations applied (an unused SQLite path; a fresh `CREATE DATABASE` without a template), for the startup and migration tests;
  - `engine` (from `create_db_engine(database_url)`, disposed afterwards) and `session` (a `sqlmodel.Session(engine)`) fixtures;
  - the `client` fixture made **function-scoped**: `monkeypatch.setenv("DATABASE_URL", database_url)`, then `with TestClient(app) as test_client: yield test_client`, so `lifespan` resolves, guards and (from US2) counts exactly as in production.

  Existing tests in `tests/integration/test_home.py` and `test_health.py` keep their signatures and now run once per engine (depends on T009, T010, T013, T016)
- [X] T008 [P] Write `tests/integration/test_startup.py`: with `DATABASE_URL` set to `empty_database_url` (no migrations applied), entering `TestClient(app)` raises `RuntimeError` whose message contains `uv run alembic upgrade head` and does **not** contain the database URL; with `RENDER=true` and no `DATABASE_URL`, entering `TestClient(app)` raises `DatabaseConfigError` whose message contains `DATABASE_URL is required` ([contracts/http-routes.md → Application startup](./contracts/http-routes.md#application-startup-the-effective-readiness-gate))

### Implementation

- [X] T009 Add `resolve_database_url(environ: Mapping[str, str] = os.environ) -> str`, `DatabaseConfigError(RuntimeError)`, `PROJECT_ROOT` (the parent of the `app` package) and `DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "student_competitions.sqlite3"` to `app/core/config.py`, exactly per [contracts/configuration.md](./contracts/configuration.md): empty string counts as unset; parse with `sqlalchemy.engine.make_url` and re-raise any parse error as `DatabaseConfigError("DATABASE_URL is not a valid database URL.") from None`; supported schemes `sqlite`, `postgres`, `postgresql`, `postgresql+psycopg`; rewrite the first two to `postgresql+psycopg` with `url.set(drivername=...)` and render with `render_as_string(hide_password=False)`; any other scheme raises `DatabaseConfigError("DATABASE_URL uses unsupported scheme '<scheme>'; expected sqlite or postgresql.")`; unset with any non-empty `RENDER` raises `DatabaseConfigError("DATABASE_URL is required when running on Render; refusing to fall back to a local SQLite file.")`; otherwise create `data/` (`mkdir(parents=True, exist_ok=True)`) and return `sqlite:///<absolute path>`. Update the module docstring, which currently says the app reads only the commit stamps from the environment, and note the portability rule (another host adds its always-set variable to the guard)
- [X] T010 [P] Create `app/core/db.py` per [research D8](./research.md#d8--timestamps-one-utc-aware-column-type-for-both-engines) and [D10](./research.md#d10--home-page-rendering-the-list-and-surviving-a-database-blip): set `SQLModel.metadata.naming_convention` to `{"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}` at import time (before any model is defined); `UTCDateTime(TypeDecorator)` with `impl = DateTime(timezone=True)` and `cache_ok = True` whose bind step raises `ValueError` on a naive datetime and converts aware values to UTC, and whose result step tags a naive value (SQLite) as UTC and converts an aware one (PostgreSQL) to UTC; `utc_now() -> datetime` returning `datetime.now(UTC)`; `create_db_engine(url: str) -> Engine` with `pool_pre_ping=True` and `hide_parameters=True`, plus `connect_args={"check_same_thread": False}` for SQLite and `{"connect_timeout": 5}` for PostgreSQL; and a FastAPI dependency `get_session(request: Request) -> Iterator[Session]` yielding `Session(request.app.state.engine)`
- [X] T011 [P] Create `app/models/question.py` with SQLModel table `Question` (`__tablename__ = "questions"`) per [data-model.md §1](./data-model.md#1-question--table-questions): `id: int | None` — "`INTEGER`, primary key, autoincrement", "assigned by the database"; `text: str` — "`VARCHAR(1000)`", "Null: no" (`sa_column=Column(String(1000), nullable=False)`); `reference_answer: str` — "`VARCHAR(5000)`", "Null: no", "**Never rendered on a public page**"; `created_at: datetime` — "`UTCDateTime`", "Null: no", "`utc_now()` at creation", "Never changes after creation"; `updated_at: datetime` — "`UTCDateTime`", "Null: no", "`utc_now()` at creation; reset to `utc_now()` by every update". Use `Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)` (or an equivalent explicit `sa_column`) for both timestamps. No relationships and no index (depends on T010)
- [X] T012 [P] Create `app/models/boot_counter.py` with SQLModel table `BootCounter` (`__tablename__ = "boot_counter"`) per [data-model.md §2](./data-model.md#2-bootcounter--table-boot_counter): `id: int` — "`INTEGER`, primary key, `CHECK (id = 1)`", "Always `1`. The check makes a second row impossible" (`__table_args__ = (CheckConstraint("id = 1", name="single_row"),)`, which the naming convention turns into `ck_boot_counter_single_row`); `boots: int` — "`BIGINT`", "Null: no", "Starts at `0`… Only ever incremented" (depends on T010)
- [X] T013 Create `app/models/__init__.py` importing `Question` and `BootCounter` (with `__all__`) so that importing `app.models` makes `SQLModel.metadata` complete, and delete `app/models/.gitkeep` (depends on T011, T012)
- [X] T014 Create `migrations/env.py` per [research D3, D5, D14](./research.md#d5--migration-atomicity-and-concurrent-starts): `fileConfig(config.config_file_name, disable_existing_loggers=False)` when a config file is present (otherwise calling Alembic from the tests or the app would silence application loggers); `import app.models` and `target_metadata = SQLModel.metadata`; the URL from `resolve_database_url(os.environ)`, used to build the engine directly (`create_engine(url, poolclass=NullPool)`), **never** written into `config.set_main_option` (it would be `%`-interpolated and could be logged); online mode only; `context.configure(connection=..., target_metadata=..., compare_type=True, render_as_batch=(dialect == "sqlite"))`, with `transaction_per_migration` left at its default `False`; inside `with context.begin_transaction():`, when `connection.dialect.name == "postgresql"`, execute `SELECT pg_advisory_xact_lock(:key)` with a fixed module-level 64-bit `MIGRATION_LOCK_KEY` **before** `context.run_migrations()`. Comment the lock with its justification (plan *Complexity Tracking*) (depends on T009, T013)
- [X] T015 Generate the first revision with `uv run alembic revision -m "create questions and boot counter"` (a file `migrations/versions/YYYY_MM_DD_<rev>_create_questions_and_boot_counter.py`) and write it by hand with explicit SQLAlchemy types, not the application's: `op.create_table("questions", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("text", sa.String(1000), nullable=False), sa.Column("reference_answer", sa.String(5000), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))`; `op.create_table("boot_counter", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False), sa.Column("boots", sa.BigInteger(), nullable=False), sa.CheckConstraint("id = 1", name=op.f("ck_boot_counter_single_row")))`; then `op.bulk_insert` of the single row `{"id": 1, "boots": 0}` into a frozen `sa.table("boot_counter", sa.column("id"), sa.column("boots"))`. `downgrade()` drops both tables. Primary-key constraint names must follow the naming convention so the drift test (T052) passes. Run `uv run alembic upgrade head` against the default SQLite file and confirm `data/student_competitions.sqlite3` is created (depends on T004, T005, T014)
- [X] T016 [P] Create `app/core/migrations.py` per the plan's *Structure Decision*: `alembic_config() -> Config` loading `PROJECT_ROOT / "alembic.ini"` (anchored to the project root, not the working directory); `head_revision() -> str` via `ScriptDirectory.from_config(...).get_current_head()`; `current_revision(connection) -> str | None` via `MigrationContext.configure(connection).get_current_revision()`; and `ensure_at_head(engine) -> str` that returns the revision when it equals head and otherwise raises `RuntimeError("Database is at revision <current or 'none'> but the code expects <head> — run `uv run alembic upgrade head`.")`. No database URL in any message. Keeps `app/core/db.py` free of Alembic imports (depends on T009)
- [X] T017 Add a FastAPI `lifespan` to `app/main.py`: `url = resolve_database_url(os.environ)`; `engine = create_db_engine(url)`; `revision = ensure_at_head(engine)`; `app.state.engine = engine`; log once at `INFO` the dialect name and revision only (never the URL); `yield`; `engine.dispose()`. Pass it as `FastAPI(..., lifespan=lifespan)`. Rewrite the module docstring, which currently promises that no database is contacted at startup (depends on T009, T010, T016)
- [X] T018 Update `Dockerfile` per [contracts/pipeline.md → Container](./contracts/pipeline.md#container-dockerfile-dockerignore): `COPY alembic.ini ./` and `COPY migrations ./migrations` next to `COPY app ./app`; before `USER appuser`, `mkdir -p /app/data && chown appuser /app/data` so the default SQLite file is writable in a local `docker run`; `HEALTHCHECK --start-period=30s` (migrations now run before the port opens); `CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]`. Uvicorn must stay PID 1 via `exec`, and a failed migration must leave uvicorn unstarted. Update the header and the CMD comments to explain why migrations run in the entrypoint (no pre-deploy command on Render's free plan, [research D4](./research.md#d4--where-migrations-run-the-container-entrypoint-then-a-startup-guard)) (depends on T003, T015)
- [X] T019 In `.github/workflows/checks.yml` → `quality`, add `services.postgres` (`image: postgres:17`, `env: POSTGRES_HOST_AUTH_METHOD: trust`, `ports: ["5432:5432"]`, health check `pg_isready` with `--health-interval 2s --health-retries 15`) and job `env: TEST_POSTGRES_URL: postgresql://postgres@localhost:5432/postgres`. No password anywhere in the workflow, and still no `secrets.` reference or `environment:` ([contracts/pipeline.md → quality](./contracts/pipeline.md#quality))
- [X] T020 Run `uv run pytest` twice from the repository root, first without and then with `TEST_POSTGRES_URL` (see *Path Conventions*), then run `uv run ruff check .` and `uv run ruff format --check .`. T006 and T008 must pass, and every existing test in `test_home.py` and `test_health.py` must pass as `[sqlite]` and `[postgresql]`. Then run `CI=true uv run pytest` without `TEST_POSTGRES_URL` and confirm the session **fails at start**. Finally, run `docker build -t student-competitions .` and `docker run --rm -p 8000:8000 student-competitions`, and confirm the log shows the migration running before uvicorn starts and that `GET /` returns `200`

**Checkpoint**: The application starts only against a migrated database, the suite runs on both
engines, CI provides PostgreSQL, and the image migrates before serving. User story work can now
begin

---

## Phase 3: User Story 1 - Visitors see sample questions coming from the database (Priority: P1) 🎯 MVP

**Goal**: The public home page shows a read-only, escaped, stable-order list of the six sample
questions seeded by a migration, has a "no questions yet" state and survives a database blip with a
friendly notice. It has no write affordance of any kind.

**Independent Test**: On a freshly migrated database (local or production), open the home page and
confirm the six sample questions are listed once each, in order, with no reference answer and no
form, button or edit link.

### Tests for User Story 1 (write first, confirm they FAIL)

- [X] T021 [US1] Add a session-scoped `sample_questions` fixture to `tests/conftest.py` that reads `SAMPLE_QUESTIONS` from the seed revision's module through Alembic, walking `ScriptDirectory.from_config(alembic_config()).walk_revisions()` for the revision whose `module` has that attribute. This keeps a single source of truth, and tests never hold a copy of the sample data ([research D6](./research.md#d6--sample-questions-a-data-migration-not-startup-code))
- [X] T022 [P] [US1] Extend `tests/integration/test_home.py` with the [contracts/http-routes.md](./contracts/http-routes.md#get---home-page) cases (all engine-parametrized through `client`): `<section id="questions" aria-labelledby="questions-heading">` with `<h2 id="questions-heading">Sample questions</h2>`; one `<ol class="question-list">` whose `<li>` items equal the sample texts **in `SAMPLE_QUESTIONS` order**, each exactly once, compared with `markupsafe.escape(text)` (Jinja escapes `"` as `&#34;`, which `html.escape` does not). The Ukrainian two-line sample is present with its internal `\n` intact. **No** sample `reference_answer` appears anywhere in the body; the body has no `<form` and no `<button`, and there is no `<a` inside the list (US1-2, FR-018, FR-022). A question inserted directly through `session.add(Question(text="<b>bold</b> & more", reference_answer="x"))` renders as `&lt;b&gt;bold&lt;/b&gt; &amp; more` and never as `<b>bold</b>` (US1-5, FR-024). After `session.exec(delete(Question)); session.commit()`, the page shows `<p class="questions-empty">No questions yet.</p>` and no `<ol class="question-list">` (US1-3, FR-023). Loading the page three times shows the same list (US1-4). With `app.routers.pages.list_questions` monkeypatched to raise `sqlalchemy.exc.OperationalError("SELECT 1", {}, Exception("boom"))`, the status is still `200`, the hero `<h1>` and the footer are present, `<p class="data-unavailable" role="status">Question data is temporarily unavailable. Please try again in a moment.</p>` is present, there is no `question-list`, and neither `OperationalError`, `boom` nor `SELECT` appear in the body (FR-026). Questions are inserted directly with the `Question` model because `create_question` arrives in US4
- [X] T023 [P] [US1] Extend `tests/integration/test_health.py`: with `app.routers.pages.list_questions` monkeypatched to raise `OperationalError`, `GET /` still returns `200` with the unavailable notice **and** `GET /healthz` returns `200` with `status == "ok"` and exactly the three keys (FR-029, [quickstart V8](./quickstart.md#v8-a-database-blip-degrades-the-page-not-the-service))
- [X] T024 [P] [US1] Create `tests/integration/test_routes.py` asserting that every route in `app.routes` that has `methods` (FastAPI `APIRoute` and Starlette `Route`) has methods ⊆ `{"GET", "HEAD"}`, naming the offending path on failure, and that the static `Mount` is the only mount. Guards FR-018 and FR-033 over the whole route table. It needs no database, so it uses `app` directly, not `client`

### Implementation for User Story 1

- [X] T025 [US1] Generate the seed revision with `uv run alembic revision -m "seed sample questions"` (`migrations/versions/YYYY_MM_DD_<rev>_seed_sample_questions.py`, `down_revision` = T015's revision). Declare a module-level `SAMPLE_QUESTIONS: list[dict[str, str]]` holding the **six** rows of [data-model.md §6](./data-model.md#6-sample-questions-content-of-revision-2) verbatim, in table order, with keys `text` and `reference_answer` (row 6's `⏎` is a real `\n`; keep `°`, `₂`, the em dash and the Cyrillic text exactly). `upgrade()` inserts them with **one** `op.bulk_insert` into a **frozen** `sa.table("questions", sa.column("text", sa.String), sa.column("reference_answer", sa.String), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))`, with every row carrying the **same** `now = datetime.now(UTC)` for both timestamps, so public order is id order. `downgrade()` deletes exactly those rows (`DELETE … WHERE text IN (…)` on the frozen table). The module must **not** import anything from `app` (the migration is a frozen snapshot)
- [X] T026 [P] [US1] Create `app/schemas/question.py` with the non-table SQLModel `QuestionPublic` (`id: int`, `text: str`), the read-only view for public pages. It has **no** `reference_answer` field, so a template cannot display one (FR-022). Delete `app/schemas/.gitkeep`
- [X] T027 [P] [US1] Create `app/services/questions.py` with `list_questions(session: Session) -> list[Question]`, returning `select(Question).order_by(Question.created_at, Question.id)` (FR-016, "oldest first by creation time, ties broken by identifier") and an empty list when none are stored. Module docstring: this is the internal question interface of [contracts/question-service.md](./contracts/question-service.md), not exposed through any route, and milestone 6 must add role checks where it calls it. Delete `app/services/.gitkeep`
- [X] T028 [US1] Rewrite `home` in `app/routers/pages.py` as a **sync** `def home(request: Request, session: Session = Depends(get_session))`. It calls `list_questions(session)` inside `try`, maps each result to `QuestionPublic.model_validate(q, from_attributes=True)` and passes `questions` plus `data_available=True` to `pages/home.html`. On `sqlalchemy.exc.SQLAlchemyError` **only**, it logs one `ERROR` record with the exception type and message via a module logger (never the URL) and renders with `data_available=False`. Every other exception still reaches the default `500` handling. The handler stays thin: no query or formatting logic (depends on T026, T027)
- [X] T029 [US1] Extend `app/templates/pages/home.html` after the hero, per [contracts/http-routes.md](./contracts/http-routes.md#response-200-ok-database-reachable): when `data_available`, render `<section id="questions" aria-labelledby="questions-heading">` with `<h2 id="questions-heading">Sample questions</h2>`, then either `<ol class="question-list">` with one `<li>{{ question.text }}</li>` per item (text only, no link) or `<p class="questions-empty">No questions yet.</p>`; otherwise render `<p class="data-unavailable" role="status">Question data is temporarily unavailable. Please try again in a moment.</p>` in place of the section. No `|safe` filter on any database value
- [X] T030 [P] [US1] Add to `app/static/css/app.css`: `.question-list li { white-space: pre-line; overflow-wrap: anywhere; }` (line breaks shown, long text wraps at phone width, spec edge cases), a muted `.questions-empty` and a visible but calm `.data-unavailable` using Pico variables. Keep the file's comment style
- [X] T031 [US1] Extend the `image` job's `Smoke test GET /` step in `.github/workflows/checks.yml` to also assert the body contains `What is the boiling point of water at sea level` (the first sample question) and does **not** contain `temporarily unavailable`, printing the URL and a body excerpt on failure like the existing checks
- [X] T032 [US1] Declare the production database key in `render.yaml`: under `envVars`, add `- key: DATABASE_URL` with `sync: false` and a comment saying it holds Neon's direct connection string, is entered once in the dashboard ([quickstart N2](./quickstart.md#n2-give-the-connection-string-to-render)), and is never committed. Update the header comment, which currently says the service needs no secret. No `databases:` block and no `fromDatabase` ([contracts/pipeline.md → Render service](./contracts/pipeline.md#render-service-renderyaml))
- [X] T033 [US1] Document local setup in `README.md` (FR-011, FR-032, SC-008): add `uv run alembic upgrade head` to *Setup*/*Run* between `uv sync` and `uvicorn`, with "run it again after pulling a new migration; the app refuses to start and prints this command if you forget" and "to start over, delete `data/student_competitions.sqlite3` and migrate". In *Environment variables*, add `DATABASE_URL` (read by `app/core/config.py` and `migrations/env.py`; default `sqlite:///<repo>/data/student_competitions.sqlite3` when not on Render; **secret in production**, set only in Render's dashboard; `postgresql://` accepted and normalised) and `RENDER` (set to `true` by Render; turns a missing `DATABASE_URL` into a startup failure; do not set it locally). Replace the "none of them is secret" statement accordingly
- [ ] T034 [US1] [MANUAL] Bootstrap the production database per [quickstart.md](./quickstart.md#one-time-bootstrap-production-database) **N1** and **N2** **before this branch merges to `main`**: create the Neon project `student-competitions` (PostgreSQL 17, AWS Europe Central 1 / Frankfurt), copy the **direct** (non-pooled) connection string, re-check the free-plan limits against [research D1](./research.md#d1--managed-production-postgresql-neon-free-plan), and store the string as `DATABASE_URL` in Render → service → Environment with **Save only**. Never paste it anywhere else. If this is skipped, the first release refuses to start by design and milestone 2 keeps serving
- [X] T035 [US1] Run `uv run pytest` with `TEST_POSTGRES_URL` set: T022–T024 pass on both engines. Then validate [quickstart V1](./quickstart.md#v1-a-clean-checkout-shows-the-samples-locally-us1-1-us2-3-fr-002-fr-011-sc-008) on a fresh clone with no environment variables: `uv sync`, `uv run alembic upgrade head`, `uv run uvicorn app.main:app --reload`. The six samples are listed in order, the Ukrainian one on two lines, with no answers and no form. Check the page at phone width (browser devtools, 360 px) for no horizontal scroll

**Checkpoint**: The home page lists real data from the database, safely and read-only. This is the
milestone's headline slice and is demonstrable locally on its own

---

## Phase 4: User Story 2 - Data survives restarts and redeploys, and anyone can see that it does (Priority: P2)

**Goal**: Every application start increments a single database counter atomically, and the home
page shows `Database: <engine> · schema revision <rev> · boot #N` with machine-readable `data-*`
attributes. The CI image job proves `1 → 2` across a container restart on PostgreSQL, and every
release proves the public count went up.

**Independent Test**: Read the boot number on the home page, restart the application (or redeploy),
reload, and confirm the number is higher and the sample questions are still present exactly once.

### Tests for User Story 2 (write first, confirm they FAIL)

- [X] T036 [P] [US2] Create `tests/integration/test_boot_counter.py` (engine-parametrized) covering [question-service.md](./contracts/question-service.md#behaviour-matrix-each-row-is-a-test-run-on-sqlite-and-postgresql) rows 14–16: on a fresh clone (`boots = 0`), `record_boot` returns `1`, then `2`; **8 threads**, each with its own `Session(engine)` and started together behind a `threading.Barrier`, each calling `record_boot` → the final count is exactly `8` (FR-028); `read_database_status` twice with no boot in between returns identical `boots`. Also cover it through the app: after entering `client`, the page shows `data-boots="1"`; reloading `/` three times leaves it at `1` (US2-4); exiting and re-entering `TestClient(app)` against the same `database_url` shows `data-boots="2"` (US2-2, FR-027)
- [X] T037 [P] [US2] Extend `tests/integration/test_home.py` with the status-line contract ([http-routes.md](./contracts/http-routes.md#response-200-ok-database-reachable)): exactly one `<p class="db-status"`; `data-engine` equals the parametrized engine (`sqlite` / `postgresql`, US2-3); `data-revision` equals `head_revision()` (US2-5); `data-boots="1"`; the visible text reads `Database: SQLite` or `Database: PostgreSQL`, then `schema revision <code><head></code>`, then `boot #1`, separated by ` · `; the status line comes **after** the questions section and **before** `<footer`. When `list_questions` or `read_database_status` is monkeypatched to raise `OperationalError`, the unavailable notice replaces **both** the list and the status line (no `db-status` in the body, FR-026)
- [X] T038 [P] [US2] Extend `tests/integration/test_startup.py`: when startup is refused (database behind head; `RENDER=true` without a URL), the boot count of an otherwise migrated database is unchanged, so a refused start is not counted

### Implementation for User Story 2

- [X] T039 [US2] Create `app/services/database_status.py` per [data-model.md §4](./data-model.md#4-databasestatus--the-status-line-view) and [question-service.md → Neighbouring service](./contracts/question-service.md#neighbouring-service-appservicesdatabase_statuspy). Define `@dataclass(frozen=True) class DatabaseStatus(engine: str, revision: str | None, boots: int)` with a `display_name` property mapping `sqlite` → `"SQLite"` and `postgresql` → `"PostgreSQL"` (other names are returned unchanged). `record_boot(session) -> int` executes **one** `update(BootCounter).where(BootCounter.id == 1).values(boots=BootCounter.boots + 1)`, raises `RuntimeError` unless `result.rowcount == 1`, commits, then reads back and returns `boots`; it never does a read-modify-write in Python. `read_database_status(session) -> DatabaseStatus` is read-only: `session.get_bind().dialect.name`, `current_revision(session.connection())` from `app/core/migrations.py`, and `boots` from `session.get(BootCounter, 1)`
- [X] T040 [US2] In the `lifespan` of `app/main.py`, after `ensure_at_head`, run `with Session(engine) as session: boots = record_boot(session)` and extend the startup log line to the dialect name, revision and boot number only. A failure propagates, so uvicorn exits and the release fails ([research D7](./research.md#d7--boot-counter-one-row-one-atomic-update-per-start)) (depends on T039)
- [X] T041 [US2] In `app/routers/pages.py`, also call `read_database_status(session)` **inside the same `try`** as `list_questions` and pass it to the template as `db_status`. A `SQLAlchemyError` from either read gives the single unavailable state (depends on T039)
- [X] T042 [US2] Add the status line to `app/templates/pages/home.html` inside the `data_available` branch, after the questions section, exactly as in the contract: `<p class="db-status" data-engine="{{ db_status.engine }}" data-revision="{{ db_status.revision }}" data-boots="{{ db_status.boots }}">Database: {{ db_status.display_name }} · schema revision <code>{{ db_status.revision }}</code> · boot #{{ db_status.boots }}</p>`. It does not appear in the unavailable state or on the error page
- [X] T043 [P] [US2] Add a muted, small `.db-status` rule to `app/static/css/app.css`, matching `.release`, with `overflow-wrap: anywhere` so the revision wraps on a phone
- [X] T044 [US2] Rework the `image` job in `.github/workflows/checks.yml` per [contracts/pipeline.md → image](./contracts/pipeline.md#image). Add the same `postgres:17` service as `quality`. Add a **Refuse without configuration** step: `docker run --rm -e RENDER=true student-competitions:ci` must exit non-zero and its output must contain `DATABASE_URL is required` (FR-004). Start the container with `docker run -d --name smoke --network host -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres student-competitions:ci`, using the **un-normalised** `postgresql://` form so the rewrite runs in the real image, and drop `-p`. Keep the existing wait and `/healthz` steps. In `GET /`, also assert `data-engine="postgresql"` and `data-boots="1"`. Add a **Restart** step: `docker restart smoke`, wait for `/healthz` again, then assert `data-boots="2"` and that the page has exactly six `<li>` items in the question list (`grep -c`), which proves persistence and no re-seed in the packaged app. Keep cleanup `if: always()`. Every failure prints the URL, the expected and found values, a body excerpt and `docker logs smoke`
- [X] T045 [P] [US2] Create executable `scripts/database_status.sh` (`set -euo pipefail`) per [contracts/pipeline.md → database_status.sh](./contracts/pipeline.md#scriptsdatabase_statussh). `boot-count <base-url>` does `GET <base-url>/` and prints the `data-boots` value, or prints nothing if there is none or the request fails, and **always exits 0**. `verify <base-url> <revision> [<previous-boots>]` retries `GET <base-url>/` for up to 60 s until it gets a `200`, then asserts that `Question data is temporarily unavailable` is absent, that `data-revision` equals `<revision>`, and, when `<previous-boots>` is non-empty, that `data-boots` is strictly greater. It logs the previous and new counts, or `no previous boot count` when none was given. Each failure prints the URL, the expected and found values and a page excerpt, and the script exits `1`. It needs no credential and prints none. Use `curl --max-time 60` (cold starts)
- [X] T046 [US2] Extend `.github/workflows/deploy.yml` → `deploy` per [contracts/pipeline.md → deploy.yml](./contracts/pipeline.md#deployyml-the-release), in this order. After checkout, add `astral-sh/setup-uv` with caching and `uv sync --locked`. Add an **Expected revision** step (`id: head`) that runs `uv run alembic heads`, fails unless exactly one line is printed, and writes the revision id (first token) to `$GITHUB_OUTPUT`. Add a **Previous boot count** step (`id: before`): `echo "boots=$(./scripts/database_status.sh boot-count "${{ vars.PUBLIC_BASE_URL }}")" >> "$GITHUB_OUTPUT"`. Keep the existing trigger and *Verify commit* steps. After them, add **Verify data**: `./scripts/database_status.sh verify "${{ vars.PUBLIC_BASE_URL }}" "${{ steps.head.outputs.revision }}" "${{ steps.before.outputs.boots }}"`. `alembic heads` reads only the script directory and never connects to a database, so no database credential enters GitHub (depends on T045)
- [X] T047 [US2] Run the suite with `TEST_POSTGRES_URL` set (T036–T038 green on both engines), then validate by hand. Locally, start `uvicorn` twice (stop and start again), reload `/` several times each run, and confirm `boot #` rose by exactly one per start and never per reload. Then run [quickstart V4](./quickstart.md#v4-the-packaged-app-migrates-persists-and-refuses-to-run-unconfigured-on-render-us2-2-us3-1-fr-004-fr-020-fr-027) against `sc-pg`: the refusal with `RENDER=true`, then `data-boots="1"`, then `2` after `docker restart`, with the samples listed once each
- [ ] T048 [US2] [MANUAL] **After this milestone merges**, witness [quickstart V6](./quickstart.md#v6-the-boot-count-rises-across-a-redeploy-us2-25-fr-009-fr-027-sc-002-automated-every-release-witness-once) (SC-002). Confirm that the first release's *Verify data* step logs `no previous boot count` and checks the revision. Note the public `data-boots`, merge any trivial pull request, and confirm that its *Verify data* step logs a strictly higher count and that all six samples are still present exactly once

**Checkpoint**: Persistence is observable by anyone on the page and asserted by the pipeline on
every pull request (restart) and every release (redeploy)

---

## Phase 5: User Story 3 - The data structure evolves safely through versioned migrations (Priority: P3)

**Goal**: The migration history is proven correct on both engines (empty → head, idempotent
re-apply, stairway, single head, no model/migration drift, concurrency-safe on PostgreSQL), and
applied automatically and atomically on every publish.

**Independent Test**: From an empty database, apply all migrations and confirm the question table
and the sample questions exist; apply them again and confirm nothing changes; publish a release and
confirm production reports the head revision.

**Note**: the migration machinery itself (`alembic.ini`, `env.py` with the advisory lock, revision
1, the entrypoint, the startup guard) is Phase 2, because every story needs it; revision 2 is US1.
This phase is the story's remaining part: the tests that prove the guarantees, the developer
documentation, and the production failure drill.

### Tests for User Story 3 (write first; most should already PASS against Phase 2 + US1, and any that fails is a defect in that work)

- [X] T049 [P] [US3] Create `tests/integration/test_migrations.py` with a helper that runs `alembic.command.upgrade/downgrade(alembic_config(), target)` while `monkeypatch.setenv("DATABASE_URL", empty_database_url)`. Test empty → head (US3-1, SC-006): the current revision equals `head_revision()`, the `questions` and `boot_counter` tables exist, the stored `(text, reference_answer)` pairs ordered by `created_at, id` equal `sample_questions` **exactly** (the Cyrillic text and its line break round-trip unchanged, FR-017), and `boots == 0`
- [X] T050 [US3] In `tests/integration/test_migrations.py`, test head → head (US3-2, FR-008): after a second `upgrade head`, the revision, the row count (still 6), every row's content and timestamps, and `boots` are unchanged, and no error is raised (FR-020)
- [X] T051 [US3] In `tests/integration/test_migrations.py`, add the **stairway** test ([research D14](./research.md#d14--migration-housekeeping-naming-a-single-head-and-drift-detection)): for each revision in `ScriptDirectory.walk_revisions()` from base upward, `upgrade <rev>` → `downgrade -1` → `upgrade <rev>` succeeds; then `downgrade base` leaves no application tables, and `upgrade head` again gives exactly the sample questions. Also add a **single head** test: `len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1`
- [X] T052 [US3] In `tests/integration/test_migrations.py`, add the **no drift** test (FR-007): after `upgrade head`, `alembic.autogenerate.compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), SQLModel.metadata)` returns `[]` on both engines, so a model change without a migration fails CI. Fix T011, T012 or T015 rather than weakening the comparison if it reports a difference
- [X] T053 [US3] In `tests/integration/test_migrations.py`, add the **PostgreSQL-only** concurrent-upgrade test (`pytest.skip` on the `sqlite` case, citing [research D5/D12](./research.md#d5--migration-atomicity-and-concurrent-starts)): two threads started together behind a `threading.Barrier` both run `upgrade head` on the same empty database. Both succeed, `alembic_version` has exactly one row equal to head, and the sample questions are present exactly once (spec edge case "Two instances start at the same time"). Each thread must set its URL via `alembic_config().attributes` or a shared environment set before the threads start, not a per-thread `monkeypatch`

### Implementation for User Story 3

- [X] T054 [US3] Add an **Adding a migration** section to `README.md` per [quickstart.md](./quickstart.md#adding-a-migration-for-this-and-every-later-milestone): change or add a model in `app/models/` and import it in `app/models/__init__.py`; `uv run alembic revision --autogenerate -m "short description"`; read and fix the generated file; `uv run alembic upgrade head`; `uv run pytest` (drift, single-head and stairway tests guard the history). State the binding rule from [research D4](./research.md#d4--where-migrations-run-the-container-entrypoint-then-a-startup-guard): a migration must keep the **previous** release working during a deploy overlap (expand now, contract in a later release); data migrations use a frozen `sa.table`, never app imports; migrations run automatically in the container entrypoint on every release, with no manual production commands; on PostgreSQL the whole upgrade is one transaction behind an advisory lock; a failed local SQLite migration may be partial, so fix it and re-run, or delete the file
- [X] T055 [US3] Run `uv run pytest` with `TEST_POSTGRES_URL` set and confirm the [quickstart V2](./quickstart.md#v2-the-suite-proves-operations-and-migrations-on-both-engines-us3-125-us4-fr-005-fr-008-fr-030-sc-003-sc-006) shape: every test in `test_migrations.py` appears as `[sqlite]` and `[postgresql]`, and the concurrent-upgrade test is the only one skipped on SQLite
- [ ] T056 [US3] [MANUAL] **After this milestone merges and its first release is green**, run [quickstart V7](./quickstart.md#v7-a-failing-migration-leaves-production-untouched-us3-4-fr-010-sc-007-manual-required-once) (SC-007, FR-010). On a throwaway branch, add an empty revision whose `upgrade()` creates a table `sc007_probe` and then does `if os.environ.get("RENDER"): raise RuntimeError("SC-007 probe")`. CI passes; merge it. Confirm that Deploy fails at *Verify commit*, that Render's deploy log shows the `RuntimeError`, and that the public page still shows the **previous** revision and all samples. In Neon's SQL editor, confirm `SELECT to_regclass('sc007_probe');` is `NULL` and `alembic_version` holds the previous head. Revert the probe on `main` immediately and confirm the revert's release is green

**Checkpoint**: The migration history is guarded by CI on both engines, and a bad migration cannot
take production down or half-apply

---

## Phase 6: User Story 4 - Question operations are proven correct on both database engines (Priority: P4)

**Goal**: The internal create / get / list / update / delete interface for questions that
milestones 6 and 8 build on, with input validation at the schema boundary and an explicit
not-found outcome, verified row by row on SQLite and PostgreSQL.

**Independent Test**: Open a pull request; confirm the question-operation tests run on both
engines and pass; introduce a deliberate defect in one operation and confirm the checks fail and
the pull request cannot be merged.

**Note**: `list_questions` already exists (US1). This story adds the other four operations, the
write schemas, and the full behaviour matrix.

### Tests for User Story 4 (write first, confirm they FAIL)

- [X] T057 [P] [US4] Create `tests/unit/test_question_schemas.py` per [data-model.md §1 *Validation rules*](./data-model.md#validation-rules-enforced-by-the-schemas-in-3-before-any-database-access) and §3, covering behaviour-matrix rows 7, 8, 10 and 12. `QuestionCreate` with `text` or `reference_answer` of `""`, `"   "` or `"\n\t"` raises `pydantic.ValidationError` (required; "Non-blank after stripping"). A missing field raises. `text` of 1,001 and `reference_answer` of 5,001 characters **after stripping** raise ("Maximum length (Unicode code points, after stripping) — 1,000 / 5,000"), using Cyrillic `"я"` so bytes ≠ code points. Exactly 1,000 / 5,000 Cyrillic characters, with surrounding spaces added, are accepted. `"  Line one\nLine two  "` becomes `"Line one\nLine two"` ("Surrounding whitespace — stripped before every other check and before storing"; "Internal content — stored exactly: line breaks, Cyrillic, `<`, `&` untouched"). `"<b>bold</b> & more"` is unchanged. `QuestionUpdate()` and `QuestionUpdate(text=None, reference_answer=None)` raise ("**at least one** field must be given"). `QuestionUpdate(text="x")` is valid with `reference_answer is None`, and a blank or over-long field given to `QuestionUpdate` raises like `QuestionCreate`
- [X] T058 [P] [US4] Create `tests/integration/test_question_service.py` implementing **every** row of the [behaviour matrix](./contracts/question-service.md#behaviour-matrix-each-row-is-a-test-run-on-sqlite-and-postgresql) rows 1–13 through the engine-parametrized `session` fixture. Control the clock with `monkeypatch.setattr("app.services.questions.utc_now", ...)`: row 3 creates two questions with **equal** `created_at` and asserts id order among them, after the seeded samples; row 4 advances the clock before `update_question`. Row 1: create, then `get_question` returns identical `text` and `reference_answer`. Row 2: ids differ. Row 3: `list_questions` order is `created_at, id` and stable across calls. Row 4: updating `text` only changes `text`, leaves `reference_answer` and `created_at` unchanged and advances `updated_at`. Row 5: after delete, `get` raises `QuestionNotFound` and `list` omits the question. Row 6: `get`, `update` and `delete` of a non-existent id each raise `QuestionNotFound` whose message contains the id, with the row count unchanged. Row 7: building an invalid schema raises before any service call, and the row count and stored values are unchanged. Row 9: 1,000 / 5,000 Cyrillic characters stored and returned unchanged on both engines, which also proves PostgreSQL's `VARCHAR` counts characters. Rows 10–11: round-trip exactly. Row 13: `created_at` and `updated_at` read back from a **new** session are timezone-aware with `utcoffset() == timedelta(0)` on both engines (FR-006). Also assert that `QuestionNotFound` subclasses `LookupError`

### Implementation for User Story 4

- [X] T059 [US4] Add `QuestionCreate` and `QuestionUpdate` to `app/schemas/question.py` as non-table SQLModel models, using `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]` for `text` and the same with `max_length=5000` for `reference_answer`, so stripping happens before the length checks and lengths count code points. `QuestionCreate`: both fields required. `QuestionUpdate`: both `… | None = None`, plus a `model_validator(mode="after")` raising `ValueError("at least one of text or reference_answer must be given")` when both are `None`. Put the limits in module constants `QUESTION_TEXT_MAX_LENGTH = 1000` and `REFERENCE_ANSWER_MAX_LENGTH = 5000`, and use them in `app/models/question.py`'s column lengths too, so the schema and the column cannot drift (research D9)
- [X] T060 [US4] Add to `app/services/questions.py` per [contracts/question-service.md](./contracts/question-service.md#functions): `class QuestionNotFound(LookupError)` whose `__init__(question_id)` stores the id and gives the message `Question <id> not found`. `create_question(session, data: QuestionCreate) -> Question` sets `created_at = updated_at = utc_now()` (one call), adds, commits, refreshes and returns. `get_question(session, question_id) -> Question` uses `session.get` and raises `QuestionNotFound`, never returning `None`. `update_question(session, question_id, data: QuestionUpdate) -> Question` gets or raises, sets each field in `data.model_dump(exclude_none=True)`, sets `updated_at = utc_now()`, commits, refreshes and returns. `delete_question(session, question_id) -> None` gets or raises, deletes and commits. Import `utc_now` into the module namespace (`from app.core.db import utc_now`) so tests patch `app.services.questions.utc_now`. Each write function is one committed unit of work, and the caller owns the session (depends on T059)
- [X] T061 [US4] Add a *Test* section update to `README.md` (FR-030, FR-032): `uv run pytest` runs the SQLite cases and skips the PostgreSQL ones with a reason. To run both engines the way CI does, start the password-less `postgres:17` container and set `TEST_POSTGRES_URL` (the three commands from [quickstart.md](./quickstart.md#running-the-suite-on-both-engines)). The suite creates and drops its own uniquely named databases and never touches `data/` or `DATABASE_URL`. CI fails if `TEST_POSTGRES_URL` is missing. Add `TEST_POSTGRES_URL` to the environment variable table as **tests only, never read by the application, not secret**
- [X] T062 [US4] Run `uv run pytest` with `TEST_POSTGRES_URL` set and confirm T057 and T058 pass, and that every case in `test_question_service.py` appears as both `[sqlite]` and `[postgresql]` (SC-003)
- [ ] T063 [US4] [MANUAL] **After this milestone merges**, run [quickstart V3](./quickstart.md#v3-pull-requests-run-both-engines-and-a-defect-blocks-the-merge-us4-7-fr-030-sc-003-sc-004-sc-009-manual-required-once) (SC-004, SC-009). Open a throwaway pull request changing `list_questions` to order by `Question.id.desc()`. Confirm that `checks / quality` fails, that the log shows the failing case for **both** `[sqlite]` and `[postgresql]`, and that the merge button stays disabled. Push a fix, confirm green, and confirm that the `quality` and `image` job durations are each under 10 minutes. Close the pull request without merging

**Checkpoint**: The question interface milestone 6 will call is complete, validated at its
boundary, and proven on both engines

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The cross-story performance check, documentation, credential review and acceptance

- [X] T064 Add the 500-question case to `tests/integration/test_home.py` (SC-005, [quickstart V9](./quickstart.md#v9-500-questions-still-load-fast-sc-005-edge-case)). Using the `session` fixture, create 500 questions with `create_question` (text `f"Question {i:03d}"`, a short answer), then time `client.get("/")`. It returns `200` in under 3 s, lists exactly **506** `<li>` items with the six samples first and the 500 following in creation order. Runs on both engines (needs US1 and US4)
- [X] T065 [P] Update `README.md` *Repository layout* (add `alembic.ini`, `migrations/` with `env.py` and `versions/`, `app/models/`, `app/schemas/`, `app/services/`, `app/core/db.py`, `app/core/migrations.py`, `scripts/database_status.sh`, and git-ignored `data/`) and *Tech stack* (SQLModel, Alembic, psycopg 3, SQLite locally and in tests, PostgreSQL 17 on Neon's free plan in production). In *Deployment*, add a note that releases run `alembic upgrade head` before the new version serves and that the deploy job verifies the head revision and a rising boot count. Mention credential rotation (Neon → reset password → update `DATABASE_URL` in Render → *Save, rebuild, and deploy*)
- [X] T066 Confirm there is **no** `create_all(` anywhere in the repository (`git grep -n create_all` is empty; Principle VII) and no `|safe` in `app/templates/` (FR-024)
- [X] T067 Validate [quickstart V10](./quickstart.md#v10-no-database-credential-anywhere-fr-032-sc-010-manual-required-once) (FR-032, SC-010), part 1, before merging: `git diff main...003-database-questions` contains no `neon.tech` host, no password, and no `DATABASE_URL=` with a value other than the password-less CI URLs; `checks.yml` still has no `secrets.` and no `environment:`; `pull_request_target` appears nowhere; after `docker build -t student-competitions .`, `docker run --rm --entrypoint sh student-competitions -c 'grep -r neon.tech /app || true'` prints nothing and `ls /app` shows no `data/*.sqlite3` copied from the host
- [X] T068 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` (with `TEST_POSTGRES_URL` set) from the repository root one final time and confirm all three are green. Stop and remove the local `sc-pg` container
- [ ] T069 [MANUAL] **After the milestone's first release is green**: validate [quickstart V5](./quickstart.md#v5-production-shows-the-samples-to-the-outside-world-us12-fr-021-fr-022-sc-001-manual-required-once) (SC-001, SC-005) from a device **outside** the development network. The six samples appear once each, in order, with the Ukrainian text intact, followed by `Database: PostgreSQL · schema revision <head> · boot #N`. There are no answers and no forms, the page has no horizontal scroll at phone width, and a warm reload takes under 3 s. Then complete V10 part 2: the first release's Deploy workflow log and Render deploy log contain neither `neon.tech` nor the role's password
- [ ] T070 Work through the **Milestone acceptance checklist** in [quickstart.md](./quickstart.md#milestone-acceptance-checklist) and tick N1–N2, V1–V10 and the README item. The milestone's stated criterion is "CRUD tests pass on SQLite and Postgres in CI; in production, the sample questions are visible and the boot count increases across a redeploy"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Start immediately
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories**, and must land as a
  unit: once `lifespan` requires a migrated database (T017), the fixtures (T007), CI's PostgreSQL
  (T019) and the entrypoint (T018) are all needed for anything to be green
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3/US4
- **User Story 2 (Phase 4)**: Depends on Foundational. Independent of US1's code, but its
  **templates overlap**: T041/T042 edit the same `pages.py` and `home.html` that T028/T029 create
  the questions part of, so do US2 after US1 or coordinate the two edits. T044 reworks the `image`
  job that T031 extended
- **User Story 3 (Phase 5)**: Depends on Foundational **and US1** (the sample-question assertions
  need revision 2 and the `sample_questions` fixture from T021)
- **User Story 4 (Phase 6)**: Depends on Foundational and **US1's** `app/services/questions.py` and
  `app/schemas/question.py` (T026, T027), which it extends. Behaviour-matrix row 3 relies on the
  seeded samples preceding new rows
- **Polish (Phase 7)**: T064 needs US1 and US4; the rest needs all stories complete
- **Post-merge [MANUAL] tasks** (T048, T056, T063, T069) need the milestone merged to `main` and
  T034 done; T056 and T063 each involve a throwaway pull request

### User Story Dependencies

```text
Setup → Foundational ─┬─→ US1 (P1) ─┬─→ US3 (P3) ─┐
                      │             ├─→ US4 (P4) ─┼─→ Polish → merge → post-merge MANUAL checks
                      └─→ US2 (P2) ─┘ (same files) ┘
```

US1 is the first story because the others reuse what it creates (revision 2, the question
service module, the home page section). Each later story still delivers and tests its own
increment on its own.

### Within Each Phase

- **Phase 1**: T001 first; T002 before anything that imports SQLModel/Alembic; T003–T005 together
- **Phase 2**: tests T006, T008 first (T007 needs T009, T010, T013, T016 to import); T009 and T010
  before T011/T012; T013 after both models; T014 after T009+T013; T015 after T014; T016 after
  T009; T017 after T010+T016; T018 after T015; T020 last
- **Phase 3**: T021 before T022; tests T022–T024 before T025–T029; T026, T027 before T028; T028
  before T029; T034 any time before merge; T035 last
- **Phase 4**: tests T036–T038 first; T039 before T040, T041; T041 before T042; T045 before T046;
  T047 before T048
- **Phase 5**: T049 creates `test_migrations.py`; T050–T053 add to it in sequence (hence no [P]);
  T054 anytime; T055 after tests; T056 post-merge
- **Phase 6**: T057, T058 first; T059 before T060; T062 after T060; T063 post-merge

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 together
- **Phase 2**: T006 and T008 (tests); then T010 alongside T009; then T011 and T012 together; T016
  alongside T014/T015
- **Phase 3**: T022, T023, T024 (three test files); then T026, T027, T030 together
- **Phase 4**: T036, T037, T038 (tests); T043 and T045 alongside the service work
- **Phase 6**: T057 and T058 together
- **Phase 7**: T065 alongside T064
- Across stories: once US1 lands, **US3 and US4 can proceed in parallel** (different files except
  `README.md`)

`README.md` is edited by T033 (US1), T054 (US3), T061 (US4) and T065 (Polish), never in parallel
with each other. `.github/workflows/checks.yml` is edited by T019, T031 and T044 in that order.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Tests that need no database fixtures, together:
Task: "Write tests/unit/test_database_config.py — every resolution row, guard, no URL in messages"
Task: "Write tests/integration/test_startup.py — refuses when behind head / on Render without URL"

# After T010, the two table models are independent files:
Task: "Create app/models/question.py — Question, VARCHAR(1000)/VARCHAR(5000), UTCDateTime"
Task: "Create app/models/boot_counter.py — BootCounter, CHECK (id = 1), BIGINT boots"
```

## Parallel Example: User Story 1

```bash
# Three test files together:
Task: "Extend tests/integration/test_home.py — list, order, escaping, empty, unavailable"
Task: "Extend tests/integration/test_health.py — 200 while the database is failing"
Task: "Create tests/integration/test_routes.py — every route ⊆ {GET, HEAD}"

# Then the independent building blocks:
Task: "Create app/schemas/question.py — QuestionPublic"
Task: "Create app/services/questions.py — list_questions"
Task: "Add .question-list / .questions-empty / .data-unavailable to app/static/css/app.css"
```

## Parallel Example: after US1

```bash
Developer A: US2 — database_status service, lifespan boot, status line, image restart, deploy verify
Developer B: US3 — test_migrations.py, README "Adding a migration"
Developer C: US4 — QuestionCreate/QuestionUpdate, create/get/update/delete, behaviour matrix
```

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: Setup (dependencies, Alembic scaffolding)
2. Phase 2: Foundational (URL resolution, engine, models, revision 1, startup guard, both-engine
   fixtures, CI PostgreSQL, migrating entrypoint)
3. Phase 3: User Story 1 (seed revision, `list_questions`, the home page list)
4. **STOP and VALIDATE**: quickstart V1 locally (T035). The page shows real rows from a migrated
   database on both engines

### Incremental Delivery

1. Setup + Foundational → the app has a database it can trust (migrated, guarded, tested on both
   engines)
2. **+ US1 → visitors see sample questions from the database** (MVP)
3. + US2 → persistence is visible (boot count) and asserted on every PR and release
4. + US3 → the migration history is guarded (drift, stairway, single head, concurrency)
5. + US4 → the question interface for milestone 6 exists and is proven on both engines
6. + Polish → performance, documentation, credential review
7. Merge → post-merge checks (V3, V5, V6, V7, V10 part 2) → acceptance checklist

The milestone ships as **one** pull request (constitution *Branching*), so "incremental" here means
checkpoints on the branch. Each one leaves the suite green and the app runnable.

---

## Notes

- **[MANUAL] tasks are not optional.** T034 is a one-time platform bootstrap that must happen
  **before merge**, or the first release fails by design. T048, T056, T063 and T069 are the
  post-merge acceptance procedures that the plan's *Complexity Tracking* justifies as procedures
  rather than tests
- **Two values do not exist until they are generated**: the two Alembic revision ids (T015, T025)
  and the Neon connection string (T034). The string must never be written into any file, issue,
  commit or log
- The sample-question content is frozen once revision 2 has been applied anywhere shared. Edit the
  wording in T025 before the first CI run if needed, never afterwards
- `[P]` tasks touch different files and depend on nothing unfinished
- Commit after each task or logical group. Stop at any checkpoint to validate the story
  independently
