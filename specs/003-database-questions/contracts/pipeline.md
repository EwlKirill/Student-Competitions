# Pipeline & Packaging Contract: changes for milestone 3

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](../plan.md)

Deltas to milestone 2's [container](../../002-public-deploy-cicd/contracts/container.md),
[Render service](../../002-public-deploy-cicd/contracts/render-service.md) and
[pipeline](../../002-public-deploy-cicd/contracts/pipeline.md) contracts. Anything not mentioned
here is unchanged. Rationale:
[research D4](../research.md#d4--where-migrations-run-the-container-entrypoint-then-a-startup-guard),
[D12](../research.md#d12--tests-on-both-engines-one-parametrized-fixture-template-and-clone-isolation),
[D13](../research.md#d13--pipeline-the-image-is-smoke-tested-against-postgresql-and-every-release-checks-the-data).

---

## Container (`Dockerfile`, `.dockerignore`)

| Aspect | Milestone 2 | Milestone 3 |
|---|---|---|
| Copied into the runtime stage | `.venv`, `app/` | `.venv`, `app/`, **`alembic.ini`, `migrations/`** |
| Writable paths | none | **`/app/data`**, owned by `appuser`. Holds the default SQLite file for a local `docker run` with no configuration; unreachable on Render (guard) |
| Entrypoint | `exec uvicorn …` | `alembic upgrade head && exec uvicorn …` (same host/port expansion; uvicorn still becomes PID 1) |
| `HEALTHCHECK --start-period` | 10 s | 30 s, since migrations now run before the port opens |
| `.dockerignore` | excludes `migrations/` | **stops excluding `migrations/`**; newly excludes `data/`, `*.sqlite3`, `*.db` (a developer's local database never enters an image) |
| Environment | `PORT`, `HOST`, `APP_COMMIT` | + `DATABASE_URL` (optional locally, required on Render); see [configuration.md](./configuration.md) |

**Exit behaviour**: a migration failure or configuration error exits the container non-zero
before the port opens. This is what makes a bad release fail on Render instead of serving.

## Render service (`render.yaml`)

```yaml
    envVars:
      - key: HOST
        value: 0.0.0.0
      # Neon's direct connection string, entered once in the dashboard (quickstart N2).
      # `sync: false` declares the key without a value: nothing secret is ever committed.
      - key: DATABASE_URL
        sync: false
```

No `databases:` block and no `fromDatabase`: the database is hosted by Neon, not Render
([research D1](../research.md#d1--managed-production-postgresql-neon-free-plan)). Plan, region,
health-check path, branch and `autoDeployTrigger: "off"` are unchanged. `preDeployCommand` is
**not** used because the free instance type does not offer it.

## `checks.yml`: the verification jobs

### `quality`

| Addition | Contract |
|---|---|
| `services.postgres` | `image: postgres:17`, `env: POSTGRES_HOST_AUTH_METHOD: trust`, port `5432:5432`, health check `pg_isready` (interval 2 s, retries 15) |
| Job `env` | `TEST_POSTGRES_URL: postgresql://postgres@localhost:5432/postgres` (no password anywhere) |
| Steps | unchanged: `uv sync --locked`, `ruff check .`, `ruff format --check .`, `pytest`. Pytest now runs every database test on both engines, and fails at session start if `TEST_POSTGRES_URL` is missing under `CI=true` |

### `image`

| Step | Assertion |
|---|---|
| Service | same `postgres:17` service as `quality` |
| Refuse without configuration | `docker run --rm -e RENDER=true student-competitions:ci` exits **non-zero** and its output contains `DATABASE_URL is required` (FR-004) |
| Start | `docker run -d --name smoke --network host -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres student-competitions:ci` |
| Wait | unchanged polling of `http://127.0.0.1:8000/healthz` (the port opens only after migrations and startup succeed) |
| `GET /healthz` | unchanged assertions |
| `GET /` | `200`; contains the application name (unchanged); contains the first sample question's text; `data-engine="postgresql"`; `data-boots="1"`; does **not** contain the unavailable notice |
| Restart | `docker restart smoke`, wait again, then `GET /` shows `data-boots="2"`, with the sample questions present exactly once each: persistence and "no re-seed" in the real image (US2, FR-020) |
| Cleanup | `docker rm -f smoke` (`if: always()`) |

Required status contexts stay `checks / quality` and `checks / image`; branch protection is
unchanged.

## `deploy.yml`: the release

| Step (in order) | Contract |
|---|---|
| checks | unchanged (reusable `checks.yml`) |
| checkout, **setup-uv, `uv sync --locked`** | new: needed to read the expected head revision |
| **Expected revision** | `uv run alembic heads` must print exactly one head; its id is stored as a step output |
| **Previous boot count** | `scripts/database_status.sh boot-count "$PUBLIC_BASE_URL"` prints the live `data-boots`, or nothing if the live release has no status line or does not answer. Never fails the job |
| Trigger | unchanged: `scripts/render_deploy.sh <sha>` |
| Verify commit | unchanged: `scripts/wait_for_release.sh <url> <sha>` |
| **Verify data** | `scripts/database_status.sh verify "$PUBLIC_BASE_URL" <expected-revision> [<previous-boots>]` |

### `scripts/database_status.sh`

| Subcommand | Behaviour | Exit |
|---|---|---|
| `boot-count <base-url>` | `GET <base-url>/`, print the `data-boots` value, or print nothing | always `0` |
| `verify <base-url> <revision> [<previous-boots>]` | `GET <base-url>/`, retrying for up to 60 s on a non-`200`. Then assert: the unavailable notice is absent; `data-revision` equals `<revision>`; if `<previous-boots>` is given, `data-boots` is strictly greater. Every failure prints the URL, the expected and found values, and an excerpt of the page. | `0` when all hold, `1` otherwise |

The script reads only public HTML. It needs no credential and prints none.

## Secrets surface after this milestone

| Secret | Where it lives | Reachable from |
|---|---|---|
| `RENDER_DEPLOY_HOOK_URL` | GitHub `production` environment | unchanged: the deploy job only |
| Neon connection string | Render service environment (`DATABASE_URL`) | the running service only. **Not in GitHub**, not in the repository, not in the image, never logged |

CI's PostgreSQL has no password, so the workflows contain no database credential at all (SC-010).
