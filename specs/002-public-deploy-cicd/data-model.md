# Data Model: Public Deployment & CI/CD (Milestone 2)

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](./plan.md)

**There is no persistence at this milestone.** No database, no schema, no migration, no file
written at runtime (FR-030); `app/models/` and `migrations/` stay empty until milestone 3. What
this feature *does* introduce is a small amount of state that crosses a boundary — values read
from the environment, and the payload the service reports about itself — and that is what this
document specifies.

Three "entities" in the sense that matters here: **configuration** (in), **service status** (out),
and **release identity** (the value that ties a commit to what is live).

---

## 1. Configuration (read from the environment)

Read once at import time in `app/core/config.py` and exposed as module constants. Nothing else in
the application reads `os.environ`.

| Constant | Source, in order | Type | Default | Validation | Requirement |
|---|---|---|---|---|---|
| `APP_NAME` | literal | `str` | `"Student Competitions"` | non-empty (asserted by the existing suite) | milestone 1 |
| `APP_TAGLINE` | literal | `str` | — | — | milestone 1 |
| `APP_DESCRIPTION` | literal | `str` | — | — | milestone 1 |
| `APP_VERSION` | literal | `str` | `"0.1.0"` | MUST equal `project.version` in `pyproject.toml` (asserted by `tests/unit/test_config.py`) | FR-005 |
| `COMMIT_SHA` | `APP_COMMIT` → `RENDER_GIT_COMMIT` → fallback | `str` | `"unknown"` | never empty; empty environment values fall through to the next source | FR-005, FR-025 |

**Resolution rule for `COMMIT_SHA`**, stated precisely because a test asserts it:

1. `APP_COMMIT` if set **and non-empty** — a local or CI `docker build --build-arg APP_COMMIT=…`.
   The Dockerfile declares `ARG APP_COMMIT=""`, so an unstamped build leaves it empty, and empty
   must not win.
2. otherwise `RENDER_GIT_COMMIT` if set and non-empty — supplied automatically by Render for every
   deploy, which is what makes the value correct in production without the pipeline having to
   inject it.
3. otherwise the literal `"unknown"` — the honest answer for `uv run uvicorn` in a checkout, and
   never an empty string, so a consumer can always print it.

**Not read by the application**: `PORT` and `HOST` are consumed by the container entrypoint and
passed to `uvicorn` as flags — see [contracts/container.md](./contracts/container.md). They are
listed in the README's variable table (FR-012) because they are environment values the *packaged
application* reads, but no Python code references them (research D6).

**No secrets are read by the application.** The milestone's only secret, the Render deploy hook
URL, is consumed by the pipeline, never by the app (FR-027).

---

## 2. Service status (the `/healthz` payload)

The only structured value the application emits. Full HTTP contract:
[contracts/http-routes.md](./contracts/http-routes.md#get-healthz--service-status).

```json
{
  "status": "ok",
  "version": "0.1.0",
  "commit": "9f2c1ab3e4d5678901234567890abcdef1234567"
}
```

| Field | Type | Value | Why it exists |
|---|---|---|---|
| `status` | `str` | the literal `"ok"` | Liveness. The endpoint reaches the process, so a response at all is the signal; the field makes that explicit for a human reading the JSON and gives later milestones a place to report `"degraded"` when there is a dependency to be degraded about. |
| `version` | `str` | `APP_VERSION` | The human-facing release number (FR-005). |
| `commit` | `str` | `COMMIT_SHA` — 40 hex characters on a deployed instance, `"unknown"` locally | The machine-facing release identity: what the deploy job compares against `github.sha` (FR-025, research D15). |

**Invariants**:

- The handler performs **no I/O** — no database call, no file read, no outbound request. Render's
  health check must get a 2xx within 5 seconds, and an endpoint that can be slow is an endpoint
  that can take the service down.
- The payload is a fixed set of three keys. Anything that could vary per request (uptime,
  hostname, instance id, request counts) is deliberately absent: it would make the response
  unstable to assert against and would leak infrastructure detail on an unauthenticated endpoint
  (Principle IV note in the plan).
- `status` is not computed. There is nothing to compute it from at this milestone; inventing a
  dependency check with no dependency would be an abstraction without a present need.

**Schema location**: the payload is built as a plain `dict` in the router. It is deliberately
**not** a Pydantic model in `app/schemas/` — the constitution reserves that directory for
"request/response models and LLM structured-output schemas", and a three-key literal with no
input, no validation and no variation has nothing for a schema to do. The first real request body
(milestone 4's login form) is what opens `app/schemas/`.

---

## 3. Release identity (state that lives outside the application)

Not application data, but the values the pipeline correlates. Recorded here because "which commit
is live" is the one piece of state this milestone actually manages (FR-024, FR-025, FR-026).

| Value | Produced by | Consumed by | Lifetime |
|---|---|---|---|
| `github.sha` | GitHub, per push to `main` | `scripts/render_deploy.sh` as `ref=`, and `scripts/wait_for_release.sh` as the expected value | one release |
| Render deploy id | Render, in the hook's `200` response | the workflow log — the operator's link into Render's deploy history | permanent in Render |
| `RENDER_GIT_COMMIT` | Render, at container start | `app/core/config.py` → `/healthz`'s `commit` | the life of the instance |
| GitHub deployment record (`production` environment) | the `deploy` job's `environment:` | the repository's Environments view: which commit, when, by whom, and the public URL | permanent in GitHub |

**The correlation that makes the pipeline trustworthy**: the SHA GitHub pushed, the SHA sent as
`ref`, and the SHA `/healthz` reports must be the same string. The deploy job asserts it before
reporting success, which is how "the hook returned 200" becomes "the new version is serving"
(research D15) and how "the newest commit wins" becomes observable rather than hoped for
(research D10).

---

## State transitions

The only state machine here is the release, and it belongs to the pipeline, not to the
application:

```text
commit on main
   → checks running        (quality + image)
   → checks failed ────────→ NOT PUBLISHED, previous version still live    (FR-021)
   → checks passed
   → hook called (ref=sha)
   → Render build failed ──→ NOT PUBLISHED, previous version still live    (FR-023)
   → health check failed ──→ deploy cancelled, previous version still live (FR-023)
   → /healthz reports sha ─→ PUBLISHED                                     (SC-007)
   → deadline passed ──────→ job fails loudly, state reported as unknown   (FR-023, D15)
```

Every terminal state except the last leaves visitors on a working version; the last one leaves
them on *some* working version and tells the team to go and look. There is no state in which the
public address serves a half-updated application, because Render switches traffic only after the
new instance passes its health check, and never rewrites the old one in place.
