# Implementation Plan: Public Deployment & CI/CD (Milestone 2)

**Branch**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-public-deploy-cicd/spec.md`

## Summary

Take the milestone 1 application, unchanged, and put it on the public internet with a pipeline
that keeps it there.

The application is packaged as one multi-stage Docker image (uv builder → `python:3.13-slim`,
non-root, `exec uvicorn` binding `${HOST:-0.0.0.0}:${PORT:-8000}`). It gains exactly one new
route — `GET /healthz`, returning `{"status","version","commit"}` — which serves three purposes at
once: Render's health check, the team's "what is live right now" answer, and the pipeline's proof
that a deploy landed.

The Render service is declared as code in a committed **`render.yaml` Blueprint** (free instance
type, `frankfurt`, `runtime: docker`, `healthCheckPath: /healthz`) with Render's own auto-deploy
**off**. Releases are driven entirely from GitHub Actions: a reusable `checks.yml` (ruff check,
ruff format --check, pytest, plus a Docker build and container smoke test) is called by `ci.yml`
on every pull request and by `deploy.yml` on every push to `main`. Only when those checks pass
does `deploy.yml` call Render's **deploy hook** with `ref=<commit sha>`, then poll the public
`/healthz` until it reports that same SHA — so a green workflow means the commit is actually
serving, and a failed publish leaves the previous version in place and fails loudly.

Everything the platforms allow to be code is code: the Blueprint, the three workflows, the
Dockerfile and `.dockerignore`, the two release scripts (`scripts/render_deploy.sh`,
`scripts/wait_for_release.sh`) that the workflow and a human rollback both use, and a script that
applies the branch protection rule. Three bootstrap actions genuinely cannot be: creating the
Render workspace, creating the Blueprint instance once, and copying the generated deploy hook URL
into a GitHub environment secret. Those are documented in [quickstart.md](./quickstart.md).

No user-facing behaviour changes. No new Python runtime dependency is added.

## Technical Context

**Language/Version**: Python 3.13 — unchanged from milestone 1 (`.python-version`,
`requires-python = ">=3.13,<3.14"`). The container's base images pin the same minor version.

**Primary Dependencies**: no new Python package, runtime or dev. The milestone's new dependencies
are infrastructure: Docker (multi-stage build; `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` and
`python:3.13-slim-bookworm`), GitHub Actions (`actions/checkout`, `astral-sh/setup-uv`), and
Render's free web-service tier. All three enter the stack at milestone 2 per the constitution's
stack table.

**Storage**: N/A — no database, no persistent disk, no runtime writes (FR-030). The free instance
type's ephemeral filesystem is therefore a non-issue at this milestone.

**Testing**: pytest via `fastapi.testclient.TestClient`, as in milestone 1, extended with
`tests/integration/test_health.py` (the `/healthz` contract) and `tests/unit/test_config.py`
(commit-resolution precedence and version/`pyproject.toml` agreement) — the first occupant of
`tests/unit/`. Beyond the suite, the `image` CI job builds the container and smoke-tests the
running image over HTTP, which is how "runs identically everywhere" (FR-011) is checked
automatically rather than by assertion in prose.

**Target Platform**: Linux container on Render (free web service, `frankfurt`), fronted by
Render's TLS-terminating edge. The same image runs locally under `docker run` and is the only
artifact that gets published.

**Project Type**: Single server-rendered web application — one FastAPI app, one deployment unit.
Unchanged; this milestone adds deployment and pipeline files around it, not a new component.

**Performance Goals**: warm home page under 3 s from the public address (SC-002); pull-request
verification under 5 minutes (SC-006); merge-to-live under 15 minutes (SC-007, measured by the
deploy job's own duration). A cold start after the free tier's 15-minute idle spin-down takes
about a minute and is explicitly excluded from SC-002 by the spec.

**Constraints**:

- Render free tier: 512 MB RAM, 0.1 CPU, single instance, spins down after 15 minutes idle, no
  shell access, ephemeral filesystem. The no-shell constraint is why `/healthz` reports the commit
  (D7) rather than relying on an interactive check.
- Render's health check must get a 2xx/3xx within **5 seconds**, so `/healthz` may never do work.
- No secret may appear in the repository, in the image, or in pipeline logs (FR-027); fork pull
  requests must reach no credential (FR-028).
- Every job must be time-bounded (FR-019) — no run may hang a pull request.
- Verification must install from `uv.lock` exactly (`uv sync --locked`), so a result is
  reproducible (FR-018).

**Scale/Scope**: two new application files' worth of code (a `/healthz` handler and four config
constants), ~8 infrastructure files, 2 test modules, README updates. No new abstraction, no new
service layer, no new dependency.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Verdict | Evidence / Notes |
|---|---|---|---|
| I | Walking Skeleton & Vertical Slices | **PASS** | This is milestone 2 of the ladder, on branch `002-public-deploy-cicd`, started only after milestone 1 was merged and green. It is a vertical slice through deployment: the same request path, now reaching a real visitor over the internet, guarded by checks and released automatically. Nothing from milestone 3+ is built — no SQLModel, no Alembic, no database URL, no auth (FR-030). From this milestone on, the constitution's "`main` MUST always be deployable, every merge auto-deploys" becomes mechanically true rather than aspirational. |
| II | Server-Rendered Simplicity | **PASS** | No page, template, stylesheet or JavaScript changes; the visitor sees the milestone 1 home page byte for byte. The one new route, `/healthz`, returns JSON — this is not the UI-JSON the principle forbids: it has no template, no client code and no human audience, and exists for Render's health checker and the deploy workflow (see [research.md D7](./research.md#d7--health-and-version-endpoint-healthz)). Rendering it as HTML would force both consumers to scrape markup. **No new runtime dependency is introduced**, so the principle's justification requirement has nothing to record. HTMX is still not needed and still absent. |
| III | Test-Backed Delivery (NON-NEGOTIABLE) | **PASS** | The milestone's `_Test:_` criterion — "the page is accessible from outside, the pipeline is green" — is the one criterion in the ladder that cannot live entirely inside pytest, because half of it is a statement about the internet and the other half is the pipeline itself. What *is* automated: the `/healthz` contract and the config precedence (new pytest modules); the whole suite plus `ruff check` and `ruff format --check` on every pull request and every push to `main`; a Docker build and a running-container smoke test (`/healthz` and `/` over HTTP) on every change; and the post-deploy assertion that the public address serves the deployed SHA, which fails the release job if it does not (D15). What remains manual, once before acceptance: opening the public URL from an outside device (SC-001), the deliberately-failing-test and deliberate-style-violation pull requests (SC-004, SC-005), and the deliberately broken publish (SC-008). See **Complexity Tracking** for why those three are procedures rather than tests. CI enforcement of the gate starts here, exactly as the stack table schedules it. |
| IV | Role-Based Access & Data Scoping (NON-NEGOTIABLE) | **N/A (justified)** | No roles, users, sessions or personal data exist yet (auth is milestone 4, roles milestone 5). Both public routes are deliberately anonymous: the home page is a landing page, and `/healthz` is an unauthenticated liveness endpoint by design — it exposes only a status string, the application version and the commit SHA of a repository that the pipeline configuration already ties to this address. No internal path, dependency state or configuration value is disclosed (D7 fixes the payload to three keys). |
| V | Secure Authentication & Secrets | **PASS** | No authentication is introduced, and the milestone's whole secret surface is one value: the Render deploy hook URL, held as a GitHub **environment** secret on `production` and reachable only from the deploy job on `push` to `main`. Fork pull requests run a workflow with no environment and no secret reference (FR-028). The image carries no credential (`.dockerignore` excludes `.git`, the local virtualenv and env files); the hook URL is passed to `curl` via an environment variable and never echoed (FR-027). Logs contain no secret — there are none to leak beyond the hook. |
| VI | Trustworthy LLM Evaluation | **N/A** | No LLM usage (milestone 10). |
| VII | Data Integrity & Migrations | **N/A (with a forward note)** | No database, no models, no timestamps, no `create_all()`; `migrations/` stays empty until milestone 3. The constitution's operational rule that "migrations MUST be applied as part of deployment" has nothing to apply yet — the entrypoint is a single `exec uvicorn`. Milestone 3 extends that entrypoint with an `alembic upgrade head` step; the Dockerfile is written so that this is one line in one place. |
| — | Technology Stack table | **PASS** | Exactly the three components the table schedules for milestone 2 are introduced — Docker ("one image for the whole application, configured only via environment variables"), Hosting ("Render (default)"), CI/CD ("GitHub Actions: tests + lint on every PR, every push to `main` auto-deploys") — and nothing from a later row. Python 3.13, FastAPI, Jinja2, Pico.css, uv, ruff and pytest are unchanged. |
| — | Application Layout | **PASS** | `app/` keeps its mandated shape. The new route is a thin handler in `app/routers/health.py` (parse nothing, call nothing, return a payload) and the values it reports are constants in `app/core/config.py`, where the layout already puts "settings (loaded from environment)". No service is invented for a three-key dict (Principle II, YAGNI). New top-level files — `Dockerfile`, `.dockerignore`, `render.yaml`, `.github/workflows/`, `scripts/` — are deployment infrastructure, outside `app/`, and `scripts/` is the directory the README already reserves for "developer & ops helper scripts". |
| — | Development Workflow gate 3 ("CI is green") | **PASS — now enforced** | Milestone 1 recorded a deviation here because no CI existed. This milestone closes it: `ruff check`, `ruff format --check` and the full pytest suite run on every pull request, and branch protection makes a failing run block the merge (D13, FR-016). The deviation recorded in milestone 1's plan is resolved by this feature. |
| — | Open stack decision: hosting provider | **RESOLVED** | **Render**, free instance type, region `frankfurt`. Rationale and the Railway/Fly.io comparison: [research.md D1](./research.md#d1--hosting-platform-and-plan). The managed-PostgreSQL half of that open decision belongs to milestone 3 and is deliberately left open — choosing a database offering now would be milestone-3 work smuggled into milestone 2 (Principle I). |

**New runtime dependencies**: none. Principle II's justification table is empty for this feature —
`uvicorn`, already present since milestone 1, is what the container runs.

**New infrastructure dependencies** (not Python packages, but they are things the project now
relies on, so they are named here for the same reason):

| Dependency | Where | Why it is the minimum |
|---|---|---|
| `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` | Dockerfile builder stage | uv is the project's dependency manager; using its official image avoids installing or downloading uv during the build. Build stage only — never published. |
| `python:3.13-slim-bookworm` | Dockerfile runtime stage | The smallest official image matching the pinned Python version and the builder's Debian release. |
| `actions/checkout`, `astral-sh/setup-uv` | workflows | The two actions needed to get the code and a cached uv into a runner. No third-party action handles anything security-relevant. |
| Render free web service | hosting | The constitution's default host, on the plan the user specified. |

**Post-Phase 1 re-check**: **PASS** — no verdict changed after the design artifacts were written.
The design added one route, four configuration constants, two test modules and eight
infrastructure files; it added no dependency, no abstraction, no data store and no configuration
that is not documented in [contracts/container.md](./contracts/container.md). The one design
decision that touches existing application code — anchoring the template and static directories to
the package rather than the working directory (D14) — is a correctness fix demanded by FR-011 and
changes no behaviour when the app is started from the repository root, as it always has been.

## Project Structure

### Documentation (this feature)

```text
specs/002-public-deploy-cicd/
├── plan.md                      # This file (/speckit-plan command output)
├── spec.md                      # Feature specification (/speckit-specify)
├── research.md                  # Phase 0 — D1…D15, decisions & rejected alternatives
├── data-model.md                # Phase 1 — configuration & health payload (no persistence)
├── quickstart.md                # Phase 1 — bootstrap, run & validation guide
├── contracts/
│   ├── http-routes.md           # Phase 1 — the HTTP surface, /healthz added
│   ├── container.md             # Phase 1 — image, entrypoint, environment contract
│   ├── render-service.md        # Phase 1 — render.yaml Blueprint contract
│   └── pipeline.md              # Phase 1 — workflows, triggers, secrets, exit conditions
├── checklists/
│   └── requirements.md          # Spec quality checklist
└── tasks.md                     # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
Dockerfile                          # NEW — two-stage image (uv builder → python:3.13-slim)
.dockerignore                       # NEW — keeps .git, .venv, tests, specs, docs out of context
render.yaml                         # NEW — Render Blueprint: free web service, docker, /healthz
README.md                           # CHANGED — public URL, Docker commands, env table, rollback

.github/
└── workflows/
    ├── checks.yml                  # NEW — reusable (workflow_call): `quality` + `image` jobs
    ├── ci.yml                      # NEW — pull_request → main: calls checks.yml
    └── deploy.yml                  # NEW — push → main: checks, then deploy hook, then verify

scripts/                            # (had only .gitkeep)
├── render_deploy.sh                # NEW — POST the deploy hook with ref=<sha>; used by CI and by a human rollback
├── wait_for_release.sh             # NEW — poll <public>/healthz until commit == <sha>, or fail
└── setup_branch_protection.sh      # NEW — idempotent `gh api` call applying the main-branch rule

app/
├── main.py                         # CHANGED — include the health router; static dir anchored to the package
├── core/
│   ├── config.py                   # CHANGED — + APP_VERSION, COMMIT_SHA (APP_COMMIT → RENDER_GIT_COMMIT → "unknown")
│   └── templates.py                # CHANGED — template dir anchored to the package (D14)
└── routers/
    ├── pages.py                    # unchanged
    └── health.py                   # NEW — GET /healthz → {"status","version","commit"}

tests/
├── integration/
│   ├── test_home.py                # unchanged
│   └── test_health.py              # NEW — status, content type, payload shape, version/commit
└── unit/
    └── test_config.py              # NEW — commit precedence; APP_VERSION matches pyproject.toml
```

**Structure Decision**: the milestone 1 layout is kept exactly as the constitution's *Application
Layout* fixes it; this feature adds a sibling set of deployment files at the repository root and
one new router. Three placements are worth stating explicitly:

- **`app/routers/health.py`, not a route inside `pages.py`.** `pages.py` is the server-rendered
  page surface (Jinja2 responses); `/healthz` is a machine endpoint with a different audience,
  different contract and different lifetime. Keeping them apart means the page router never grows
  a non-page concern, and a reader of `contracts/http-routes.md` can see which file owns which
  half of the surface.
- **The reported values in `app/core/config.py`, not in the router.** The layout assigns `core/`
  the "settings (loaded from environment)" role, and the constants are also what the unit test
  asserts against. The router stays a thin handler, as the layout requires.
- **`scripts/` holds the release actions, and the workflow calls them.** The alternative — inline
  `run:` blocks in the YAML — would make the rollback procedure (FR-026) a copy-paste from a
  workflow file, which is exactly how rollback procedures rot. One script, used by the pipeline
  and by a human under pressure, is tested every single release.

## Complexity Tracking

No constitution violations, no stack deviations, and no added abstraction. Two things are recorded
here because Governance requires deviations and residual risks to be visible rather than assumed
away.

| Deviation / residual risk | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| **Principle III**: four of the spec's success criteria are verified by a once-before-acceptance procedure ([quickstart.md](./quickstart.md) V1, V6, V7, V8 → SC-001, SC-004, SC-005, SC-008) rather than by an automated test. | Each of them asserts something about the *pipeline and the platform*, not about the application: that an outside device on a foreign network can reach the address; that a red check actually disables GitHub's merge button; that a broken build leaves the previous version serving. Testing them in the suite is either impossible (the suite runs *inside* the thing being tested) or requires deliberately breaking `main` on a schedule. | Automating SC-004/SC-005 would mean a job that opens a pull request containing a failing test and asserts the check fails — a bot that regularly makes the repository red, to prove that red means red. Automating SC-008 would mean deliberately shipping a broken build to production periodically. Automating SC-001 needs an external prober, which the spec places in milestone 12 ("uptime dashboards" are out of scope). What *can* be automated already is: the container runs and serves (CI `image` job), the deployed commit is the one that is live (D15), and the release fails loudly otherwise. |
| **Free-tier release window**: Render documents the zero-downtime sequence for deploys but does not state that the free instance type performs the same hand-off, and free services are single-instance — so a *successful* release may briefly restart rather than overlap. | The user specified the free plan, and the spec's own assumptions already accept idle spin-down and a slow first request. SC-008 — the criterion that actually protects visitors — is about a **failed** publish, and that is safe on any tier: a failed build or a health check that never passes ends with the old version still serving ([research.md D1](./research.md#d1--hosting-platform-and-plan)). | A paid instance type would remove the ambiguity, at a cost the milestone does not justify for an audience the spec describes as "the team and reviewers". If it ever matters, it is a one-word change to `plan:` in `render.yaml` and no code change at all — which is itself a reason to write the Blueprint now rather than click the service into existence. |
