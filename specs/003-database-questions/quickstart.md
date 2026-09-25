# Quickstart & Validation: Database & First Entity — Questions (Milestone 3)

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](./plan.md)

This guide covers how to connect the production database, how to run the application and its
suite with a database, and how to prove the milestone is done. Every validation scenario maps to
an acceptance scenario or success criterion in [spec.md](./spec.md). The run-and-configure parts
also go into the README (FR-032).

The milestone's stated criterion is **"CRUD tests pass on SQLite and Postgres in CI; in production,
the sample questions are visible and the boot count increases across a redeploy."**

## Prerequisites

| Need | For |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | Running the app, migrations and the suite (unchanged) |
| Docker | The packaged image (unchanged) and, optionally, a local PostgreSQL for the PostgreSQL half of the suite |
| A [Neon](https://neon.tech) account | The production database (one-time, N1) |
| Access to the Render service's *Environment* settings | Storing the connection string (one-time, N2) |

Locally, nothing needs configuring. The default SQLite database needs no URL, no server and no
`.env` file (FR-002, SC-008).

---

## One-time bootstrap (production database)

Do these **before** merging this milestone to `main`. If they are skipped, the first release
refuses to start (by design, FR-004), the deploy fails, and milestone 2's release keeps serving.
Nothing is lost; do the steps and re-run the deploy.

### N1: Create the Neon project

1. In Neon: **New project**. Name `student-competitions`, **PostgreSQL 17**, region **AWS Europe
   Central 1 (Frankfurt)**. It must be the same city as the Render service (`frankfurt`).
2. On the project dashboard, open **Connect**, keep the default branch and database, and turn
   **Connection pooling off**, so you get the *direct* string without `-pooler` in the host.
3. Copy the connection string. It has the form
   `postgresql://<role>:<password>@<endpoint>.eu-central-1.aws.neon.tech/<db>?sslmode=require&channel_binding=require`.
   Treat it as a password. Do not paste it into an issue, a commit, a chat or a terminal that
   logs history.
4. While on Neon's plan page, check the free-plan limits are still as recorded in
   [research D1](./research.md#d1--managed-production-postgresql-neon-free-plan) (no expiry,
   storage allowance). If they have changed, note it in the pull request.

### N2: Give the connection string to Render

1. Render → the `student-competitions` service → **Environment** → **Add environment variable**:
   key `DATABASE_URL`, value = the N1 string, pasted as is (the `postgresql://` form is
   normalised by the app).
2. Choose **Save only**. The running milestone 2 release ignores the variable, so there is nothing
   to redeploy yet.
3. `render.yaml` declares `DATABASE_URL` with `sync: false`, so Blueprint syncs keep this value and
   never overwrite it.

**Rotating the credential later**: Neon → *Roles* → reset the password → update `DATABASE_URL` in
Render → **Save, rebuild, and deploy**.

---

## Running locally

```bash
uv sync                                   # installs sqlmodel, alembic, psycopg (new)
uv run alembic upgrade head               # creates data/student_competitions.sqlite3 at head
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Run `uv run alembic upgrade head` again after pulling a branch that adds a migration. If you
forget, the app refuses to start and prints that exact command.

To start again from nothing, stop the app, delete `data/student_competitions.sqlite3`, and
migrate.

**The packaged image** (unchanged commands; the entrypoint now migrates first):

```bash
docker build --build-arg APP_COMMIT=$(git rev-parse HEAD) -t student-competitions .
docker run --rm -p 8000:8000 student-competitions        # throw-away SQLite inside the container
```

## Running the suite on both engines

```bash
uv run pytest                     # SQLite cases run; PostgreSQL cases are skipped with a reason
```

To run the PostgreSQL half too, the same way CI does:

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest
docker rm -f sc-pg                # when done
```

The suite creates and drops its own uniquely named databases on that server. It never touches
`data/` or anything `DATABASE_URL` points to (FR-031).

## Adding a migration (for this and every later milestone)

```bash
# 1. change or add a model in app/models/ (and import it in app/models/__init__.py)
uv run alembic revision --autogenerate -m "short description"
# 2. read the generated file in migrations/versions/ and fix what autogenerate got wrong
uv run alembic upgrade head
uv run pytest                     # drift, single-head and stairway tests guard the history
```

A migration must keep the **previous** release working for the few seconds both run during a
deploy: add first, remove in a later release
([research D4](./research.md#d4--where-migrations-run-the-container-entrypoint-then-a-startup-guard)).

---

## Validation scenarios

### V1: A clean checkout shows the samples locally (US1-1, US2-3; FR-002, FR-011; SC-008)

1. Fresh clone, no environment variables set. Run the three commands in *Running locally*, timing
   from `git clone`.
2. Open `http://127.0.0.1:8000`.

**Expected**: the hero, then "Sample questions" with the six sample questions in
[data-model §6](./data-model.md#6-sample-questions-content-of-revision-2) order, the Ukrainian one
on two lines; then `Database: SQLite · schema revision <head> · boot #1`. No reference answer and
no form or button anywhere. Total time under 15 minutes.

### V2: The suite proves operations and migrations on both engines (US3-1/2/5, US4; FR-005, FR-008, FR-030; SC-003, SC-006)

Run the suite with `TEST_POSTGRES_URL` set (above).

**Expected**: all green. Every test in `test_question_service.py`, `test_migrations.py`,
`test_boot_counter.py` and `test_home.py` appears twice, as `[sqlite]` and `[postgresql]`; the
only PostgreSQL-only test is the concurrent-upgrade one. Covered: the
[question-service behaviour matrix](./contracts/question-service.md#behaviour-matrix-each-row-is-a-test-run-on-sqlite-and-postgresql),
empty → head, head → head is a no-op, stairway, no model/migration drift, single head, and the home
page states in [http-routes.md](./contracts/http-routes.md).

### V3: Pull requests run both engines, and a defect blocks the merge (US4-7; FR-030; SC-003, SC-004, SC-009) *(manual, required once)*

1. Open a throwaway pull request that breaks one operation, for example
   `list_questions` ordering by `id DESC`.
2. **Expected**: `checks / quality` fails, the log shows the failing case for **both** `[sqlite]`
   and `[postgresql]`, and the merge button stays disabled.
3. Push a fix. **Expected**: green, and the `quality` job's duration plus the `image` job's
   duration are each under 10 minutes (SC-009). Close the pull request without merging.

### V4: The packaged app migrates, persists, and refuses to run unconfigured on Render (US2-2, US3-1; FR-004, FR-020, FR-027)

Automated on every pull request by the `image` job ([pipeline.md](./contracts/pipeline.md#image)).
To see it by hand against a local PostgreSQL (`sc-pg` from above):

```bash
docker run --rm -e RENDER=true student-competitions            # → exits non-zero, "DATABASE_URL is required …"
docker run -d --name m3 --network host \
  -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres student-competitions
curl -s localhost:8000/ | grep -o 'data-boots="[0-9]*"'         # → data-boots="1"
docker restart m3 && sleep 5
curl -s localhost:8000/ | grep -o 'data-boots="[0-9]*"'         # → data-boots="2", samples still listed once
docker rm -f m3
```

(`--network host` behaves this way on Linux. On Docker Desktop, use `-p 8000:8000` and
`host.docker.internal` in place of `127.0.0.1` in the URL.)

### V5: Production shows the samples to the outside world (US1-1/2; FR-021, FR-022; SC-001) *(manual, required once)*

After this milestone's release is green, open the public address from a device **outside** the
development network (for example a phone on mobile data).

**Expected**: all six sample questions, each once, in order, Ukrainian text intact; status line
`Database: PostgreSQL · schema revision <head> · boot #N`; no reference answers, no forms. The page
is readable at phone width with no horizontal scroll.

### V6: The boot count rises across a redeploy (US2-2/5; FR-009, FR-027; SC-002) *(automated every release; witness once)*

Every release's deploy job now reads `data-boots` before triggering the deploy and asserts a higher
value afterwards, together with the head revision (`database_status.sh verify`). To witness it
once:

```bash
curl -s "$PUBLIC_BASE_URL/" | grep -o 'data-boots="[0-9]*"'    # note N
# merge any trivial pull request, wait for the Deploy workflow to go green
curl -s "$PUBLIC_BASE_URL/" | grep -o 'data-boots="[0-9]*"'    # expect > N; samples still present once
```

**Expected**: the deploy job's *Verify data* step logs the previous and new counts, and the new
one is strictly higher. The first release of this milestone logs "no previous boot count"
(milestone 2 had no status line) and checks only the revision.

### V7: A failing migration leaves production untouched (US3-4; FR-010; SC-007) *(manual, required once)*

A migration that fails in CI cannot be merged (V3), so the probe must fail **only in production**:

1. On a throwaway branch, generate an empty revision whose `upgrade()` first creates a table
   `sc007_probe`, then does `if os.environ.get("RENDER"): raise RuntimeError("SC-007 probe")`.
   CI passes, because `RENDER` is unset there. Merge it.
2. **Expected**: the Deploy workflow fails at *Verify commit* (the new instance never becomes
   healthy); Render's deploy log shows the `RuntimeError`; the public page still shows the
   **previous** revision and all sample questions.
3. In Neon's SQL editor: `SELECT to_regclass('sc007_probe');` returns `NULL` (the table creation
   was rolled back with the failed revision) and `SELECT version_num FROM alembic_version;` shows
   the previous head.
4. Revert the probe commit on `main` immediately (constitution: a failed deployment is fixed or
   reverted before new feature work merges). The revert's release goes green.

> **Step 1 as written fails CI.** A probe that leaves `sc007_probe` behind off Render trips
> `test_models_match_the_migrated_schema` on both engines (autogenerate sees a table with no
> model), so the merge is blocked. Drop the table again in the same `upgrade()` when `RENDER` is
> unset, and make `downgrade()` a no-op: on Render the table is still created before the raise, so
> the rollback is still what is tested. The probe used for the recorded run was `15122e55c43b`
> (PR #13, reverted by PR #14). On the free plan the boot count may rise while the probe is
> failing: idle instances sleep and wake on the next visit, and each wake is a real boot.

### V8: A database blip degrades the page, not the service (FR-026, FR-029; edge case)

Automated: `test_home.py` forces the page's database reads to raise `OperationalError` and asserts
the friendly notice, `200`, no error detail, and `/healthz` still `200`. By hand, locally: start
the app against `sc-pg` with `DATABASE_URL`, run `docker stop sc-pg`, and reload `/`.

**Expected**: the page shows "Question data is temporarily unavailable…" in place of the list and
status line; `curl localhost:8000/healthz` still returns `{"status":"ok",…}`. Then
`docker start sc-pg`, reload, and the list and status line return with the same boot number (no
restart happened).

### V9: 500 questions still load fast (SC-005; edge case)

Automated: `test_home.py` creates 500 questions through `create_question` in the test database and
asserts `/` lists 506 items in order and responds in under 3 s. For the public address, V5's warm
reload is the measurement (open DevTools → Network → document time).

### V10: No database credential anywhere (FR-032; SC-010) *(manual, required once)*

1. `git diff main...003-database-questions` contains no `neon.tech` host, no password, and no
   `DATABASE_URL=` with a value other than the password-less CI URLs.
2. Open the first release's Deploy workflow log and the Render deploy log: neither contains the
   connection string. Search for `neon.tech` and for the role's password.
3. `docker run --rm --entrypoint sh student-competitions -c 'grep -r neon.tech /app || true'`
   prints nothing.

---

## Milestone acceptance checklist

- [X] N1 and N2 done; `DATABASE_URL` exists only in Render's environment
- [ ] V1: clean checkout → samples + status line locally in under 15 minutes
- [ ] V2: full suite green on both engines locally
- [ ] V3: defect PR fails on both engines and cannot merge; PR verification under 10 minutes
- [ ] V4: `image` job green (migrate on start, boot 1 → 2 across restart, refusal without config)
- [X] V5: samples visible from an outside device; no answers, no forms
- [X] V6: deploy job's *Verify data* green; boot count witnessed rising across a redeploy
- [X] V7: probe migration failed in production, previous version kept serving, probe table absent, revert green
- [ ] V8, V9: automated tests green
- [X] V10: no credential in the diff, the logs or the image
- [ ] README updated: local migrate command, `DATABASE_URL` / `RENDER` / `TEST_POSTGRES_URL`, running the PostgreSQL tests, adding a migration

## Reference

- Design: [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md)
- Contracts: [http-routes.md](./contracts/http-routes.md) ·
  [question-service.md](./contracts/question-service.md) ·
  [configuration.md](./contracts/configuration.md) · [pipeline.md](./contracts/pipeline.md)
