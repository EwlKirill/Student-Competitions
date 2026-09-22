---

description: "Task list for Public Deployment & CI/CD (Milestone 2)"
---

# Tasks: Public Deployment & CI/CD (Milestone 2)

**Input**: Design documents from `/specs/002-public-deploy-cicd/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle III is non-negotiable, and [plan.md](./plan.md)
names two new test modules (`tests/integration/test_health.py`, `tests/unit/test_config.py`).
Four success criteria (SC-001, SC-004, SC-005, SC-008) are verified by a once-before-acceptance
**manual procedure** rather than by pytest — see the plan's *Complexity Tracking*. Those tasks are
marked **[MANUAL]**.

**Organization**: Tasks are grouped by user story so each can be implemented and validated
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- **[MANUAL]**: A human procedure or a platform-console action; not automatable at this milestone
- Include exact file paths in descriptions

## Path Conventions

Single server-rendered web application, repository root:
`app/` (application), `tests/` (suite), `scripts/` (ops helpers), `.github/workflows/` (pipeline),
and `Dockerfile` / `.dockerignore` / `render.yaml` at the root. Unchanged from milestone 1 except
for the new deployment files.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the milestone 1 baseline and prepare the build context

- [X] T001 Confirm the milestone 1 baseline is green from the repository root: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` — all four must pass before any change is made
- [X] T002 [P] Create `.dockerignore` at the repository root excluding `.git/`, `.gitignore`, `.venv/`, `tests/`, `specs/`, `docs/`, `.github/`, `scripts/`, `migrations/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.DS_Store`, `.specify/`, `README.md` and `.env*` — per [contracts/container.md](./contracts/container.md) "Build → Context"; keeping `.git/` and env files out is what guarantees no secret reaches the image (FR-027)
- [X] T003 [P] Create an empty `tests/unit/__init__.py` so `tests/unit/` is a package like `tests/integration/`, and delete `tests/unit/.gitkeep` which it replaces

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The application code and the packaged unit that **every** user story rides on —
`render.yaml` sets `healthCheckPath: /healthz` (US1), the CI `image` job builds this Dockerfile
(US2), `wait_for_release.sh` polls `/healthz` (US3), and the container contract is US4's subject.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first, confirm they FAIL)

- [X] T004 [P] Write `tests/unit/test_config.py` asserting the `COMMIT_SHA` precedence from [data-model.md §1](./data-model.md#1-configuration-read-from-the-environment): `APP_COMMIT` wins when set **and non-empty**; an empty `APP_COMMIT` falls through to `RENDER_GIT_COMMIT`; an empty or unset `RENDER_GIT_COMMIT` yields the literal `"unknown"`; `COMMIT_SHA` is never empty. Also assert `APP_VERSION` equals `project.version` in `pyproject.toml` (read it with `tomllib`). Because `app/core/config.py` resolves at import time, reload the module under `monkeypatch.setenv`/`delenv` (`importlib.reload`) rather than importing once
- [X] T005 [P] Write `tests/integration/test_health.py` asserting the `GET /healthz` contract from [contracts/http-routes.md](./contracts/http-routes.md#get-healthz--service-status): status `200`; `content-type` is `application/json`; the body has **exactly** the three keys `status`, `version`, `commit`; `status == "ok"`; `version == APP_VERSION`; `commit` is a non-empty string. Use the existing `client` fixture from `tests/conftest.py`

### Implementation

- [X] T006 Add `APP_VERSION = "0.1.0"` and the `COMMIT_SHA` resolution to `app/core/config.py` — `os.environ.get("APP_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"`, which gives the empty-falls-through rule in [data-model.md §1](./data-model.md#1-configuration-read-from-the-environment) for free; update the module docstring, which currently states that no value is read from the environment
- [X] T007 [P] Create `app/routers/health.py` with `router = APIRouter()` and `GET /healthz` returning the plain dict `{"status": "ok", "version": APP_VERSION, "commit": COMMIT_SHA}` — a thin handler performing **no I/O of any kind** (no database, no file read, no outbound request), because Render's health check must get a 2xx within 5 seconds. Not a Pydantic schema: [data-model.md §2](./data-model.md#2-service-status-the-healthz-payload) explains why (depends on T006)
- [X] T008 [P] Anchor the template directory in `app/core/templates.py` to the package rather than the working directory: `Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")` (research [D14](./research.md#d14--templates-and-static-files-anchored-to-the-package), FR-011)
- [X] T009 In `app/main.py`, include the health router (`app.include_router(health.router)` alongside the pages router) and anchor the static mount the same way: `StaticFiles(directory=Path(__file__).resolve().parent / "static")` (D14, FR-011) (depends on T007)
- [X] T010 Run `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` from the repository root — T004 and T005 must now pass and nothing from milestone 1 may regress
- [X] T011 Create the two-stage `Dockerfile` at the repository root exactly per [contracts/container.md](./contracts/container.md) and research [D5](./research.md#d5--image-design): builder `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` copying **only** `pyproject.toml` + `uv.lock` then `uv sync --locked --no-dev --no-install-project` into `/app/.venv` with `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_PYTHON_DOWNLOADS=never`; runtime `python:3.13-slim-bookworm` receiving `/app/.venv` and `app/` and nothing else; `ARG APP_COMMIT=""` → `ENV APP_COMMIT=$APP_COMMIT`; `ENV PYTHONUNBUFFERED=1`; `WORKDIR /app`; a **non-root** user; `PATH` with the venv first; `EXPOSE 8000` (documentation only); a `HEALTHCHECK` using `python -c` against `/healthz` (there is no `curl` in the image); and `CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]` — `sh -c` so `${PORT}` expands and **`exec`** so uvicorn is PID 1 and receives `SIGTERM` directly (depends on T002, T009)
- [X] T012 Build and smoke-test the image locally: `docker build --build-arg APP_COMMIT="$(git rev-parse HEAD)" -t student-competitions .` then `docker run --rm -p 8000:8000 student-competitions`; confirm `GET /` returns `200` with the application name and `GET /healthz` returns `{"status":"ok","version":"0.1.0","commit":"<that sha>"}`

**Checkpoint**: The application serves `/healthz`, the suite is green, and the image builds and
runs — user story work can now begin

---

## Phase 3: User Story 1 - Anyone can open the application on the public internet (Priority: P1) 🎯 MVP

**Goal**: The milestone 1 home page is served from a stable public HTTPS address that anyone can
open, with the application's own 404 page on unknown paths, automatic restart after a crash, and
`/healthz` reporting what is live.

**Independent Test**: From a device outside the development environment (a phone on mobile data),
open the published address and confirm the home page renders over HTTPS.

**Note on dependencies**: this story needs the packaged image and `/healthz` from Phase 2. It does
**not** need the pipeline (US2/US3) — the first release is created by the Blueprint itself.

### Implementation for User Story 1

- [X] T013 [US1] Create `render.yaml` at the repository root declaring one service exactly per [contracts/render-service.md](./contracts/render-service.md): `type: web`, `name: student-competitions`, `runtime: docker`, `plan: free`, `region: frankfurt`, `branch: main`, `dockerfilePath: ./Dockerfile`, `dockerContext: .`, `healthCheckPath: /healthz`, `autoDeployTrigger: "off"` (**quoted** — YAML 1.1 parses a bare `off` as `false`, and the quotes are load-bearing), and `envVars` with `HOST=0.0.0.0` only. No secret may be declared here
- [X] T014 [US1] [MANUAL] Bootstrap the Render service per [quickstart.md](./quickstart.md) **B1**: create the workspace, connect the GitHub repository, **New → Blueprint** → branch `main` → `render.yaml`, deploy it, and **record the generated hostname** (Render appends a suffix if `student-competitions` is taken, so the real value is what matters). Leave Blueprint Auto-Sync **on** and code auto-deploy **off**
- [X] T015 [US1] [MANUAL] Add the repository **variable** (not secret) `PUBLIC_BASE_URL` = `https://<hostname from T014>` with no trailing slash, under GitHub → Settings → Secrets and variables → Actions → Variables (quickstart B2 step 4)
- [X] T016 [US1] Record the public address in `README.md` (FR-007) — a "Live" or "Public address" line near the top, linking `https://<hostname from T014>`
- [X] T017 [US1] Validate the public surface per [quickstart.md V2](./quickstart.md) against `https://<hostname>`: `curl -sI http://<host>` returns a 301/308 to HTTPS (FR-003); `GET /` returns `200`; `GET /about` returns `404` with `text/html`; `GET /healthz` returns the three-key payload. Open the 404 in a browser and confirm it is the **application's** friendly error page with a link home — not a Render error page and not a stack trace (FR-004, FR-029)
- [ ] T018 [US1] [MANUAL] Validate [quickstart.md V1](./quickstart.md) (SC-001, SC-002): from a device that has never run the project, on a different network, open `https://<hostname>` and confirm the styled milestone 1 home page loads over HTTPS with a valid certificate; time a **warm** reload and confirm it is under 3 seconds (a first load after 15 idle minutes is the free tier spinning up and is excluded by the spec)
- [ ] T019 [US1] [MANUAL] Validate [quickstart.md V3](./quickstart.md) (SC-011, FR-006): trigger **Manual Restart** in the Render dashboard, poll `/healthz` until it answers, and confirm the service returns on its own with `status: "ok"` and the same `commit`, with no human intervention

**Checkpoint**: The public address serves the home page over HTTPS and survives a restart — the
milestone's headline result is demonstrable on its own

---

## Phase 4: User Story 2 - A proposed change is checked automatically before it can be merged (Priority: P2)

**Goal**: Every pull request against `main` automatically runs the test suite, the style checks and
a container build/smoke test, reports the outcome on the pull request, and a failing outcome makes
the merge button unavailable.

**Independent Test**: Open a pull request with a deliberately failing test, confirm the checks
report failure and merging is blocked; fix it, confirm the checks turn green and merging becomes
possible.

**Note on dependencies**: needs Phase 2 only. It is deliverable before US1 is deployed and before
US3 exists — that independence is the point of the reusable-workflow split (research
[D9](./research.md#d9--pipeline-shape-one-reusable-checks-workflow-two-entry-points)).

### Implementation for User Story 2

- [X] T020 [US2] Create `.github/workflows/checks.yml` triggered by `workflow_call` **only**, with workflow-level `permissions: contents: read`, **no `environment:` and no `secrets.` reference anywhere** (this is what makes fork pull requests safe — FR-028), and two `ubuntu-latest` jobs per [contracts/pipeline.md](./contracts/pipeline.md): `quality` (`timeout-minutes: 10`) running checkout → `astral-sh/setup-uv` with caching → `uv sync --locked` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run pytest`; and `image` (`timeout-minutes: 15`) running checkout → `docker build --build-arg APP_COMMIT=${{ github.sha }} -t student-competitions:ci .` → run the container with a mapped port → assert `GET /healthz` is `200` with `status == "ok"` and `commit == github.sha` → assert `GET /` is `200` and contains the application name → stop the container. The smoke test must echo the URL, the status it got and an excerpt of the body on failure (FR-017)
- [X] T021 [US2] Create `.github/workflows/ci.yml` triggered by `pull_request` on `branches: [main]` (opened, synchronize, reopened), with `permissions: contents: read`, `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`, and a single job `checks` that does `uses: ./.github/workflows/checks.yml` — the `synchronize` event is what re-runs verification on new commits (FR-015)
- [X] T022 [US2] Create `scripts/setup_branch_protection.sh` — an idempotent, executable `gh api --method PUT repos/{owner}/{repo}/branches/main/protection` wrapper applying the settings table in [contracts/pipeline.md](./contracts/pipeline.md#branch-protection-the-gate-itself): required status checks `checks / quality` and `checks / image`, strict (branch must be up to date), require a pull request before merging, **0** required approvals, force pushes and deletions blocked. It must fail with a clear message if `gh` is absent or unauthenticated (research [D13](./research.md#d13--merge-protection-on-main))
- [X] T023 [US2] [MANUAL] Apply branch protection per [quickstart.md](./quickstart.md) **B3**: run `./scripts/setup_branch_protection.sh` (after `gh auth login`), or use the dashboard steps. The status-check contexts only appear in the picker **after** the workflows have run once, so open a throwaway pull request first if the list is empty. If the repository is private on a free GitHub plan the rule cannot be enforced — make it public or upgrade; there is no implementation-side workaround
- [X] T024 [US2] Validate [quickstart.md V4](./quickstart.md) (FR-013–FR-015, FR-017, SC-006): open a pull request against `main`, confirm `checks / quality` and `checks / image` start unprompted and finish within 5 minutes, push another commit and confirm both re-run, and open a failing log to confirm it names the test, or the file and the ruff rule
- [X] T025 [US2] [MANUAL] Validate [quickstart.md V6](./quickstart.md) (SC-004, FR-016): on a throwaway branch add a test asserting something false, open a pull request, and confirm `checks / quality` fails **and the merge button is disabled** — reported-but-mergeable means branch protection is not configured. Remove the failing test, confirm the checks turn green and merging becomes possible, then close the pull request without merging
- [X] T026 [US2] [MANUAL] Validate [quickstart.md V7](./quickstart.md) (SC-005, FR-014, FR-016): on a throwaway branch introduce a deliberate lint or formatting violation (an unused import, or misformatted code), open a pull request, confirm `checks / quality` fails at `ruff check` or `ruff format --check` naming the file and rule and that the merge is blocked, then close the pull request without merging

**Checkpoint**: Broken code cannot reach `main` — the gate US3 depends on is in place and proven

---

## Phase 5: User Story 3 - An accepted change reaches the public address automatically (Priority: P3)

**Goal**: A merge to `main` re-runs the same checks, then deploys the exact merged commit to Render
and asserts the public address is serving that commit — with no human action, and with the previous
version left serving if anything fails.

**Independent Test**: Make a trivial visible change (the home page description), merge it, and
confirm the public address shows it without anyone running a deployment command.

**Depends on**: US1 (the Render service and `PUBLIC_BASE_URL` must exist) and US2 (`checks.yml` is
what `deploy.yml` calls).

### Implementation for User Story 3

- [X] T027 [P] [US3] Create executable `scripts/render_deploy.sh <commit-sha>` — POSTs the deploy hook, taking the URL from the `RENDER_DEPLOY_HOOK_URL` **environment variable** (never an argument, never interpolated into a logged command line) and appending `ref=<commit-sha>` so the exact commit is built (research [D2](./research.md#d2--what-triggers-a-deploy-github-actions-calling-a-render-deploy-hook)). Accept `200` (started) and `202` (queued behind a running deploy); fail on `400`, `401`, `404` or any other status. Print the response **status and body, never the URL** (FR-027), and print the Render deploy id from the response as the operator's link into Render's deploy history. `set -euo pipefail`
- [X] T028 [P] [US3] Create executable `scripts/wait_for_release.sh <base-url> <commit-sha>` — polls `<base-url>/healthz` until the reported `commit` equals `<commit-sha>`, or fails after a **12-minute** deadline, per research [D15](./research.md#d15--proving-the-deploy-actually-landed). Each request uses `curl --max-time 60` (a free instance may be cold-starting), backs off between attempts, and the script prints the **last response it saw** before failing. `set -euo pipefail`
- [X] T029 [US3] [MANUAL] Wire the deploy hook per [quickstart.md](./quickstart.md) **B2** steps 1–3: copy the URL from Render → the service → Settings → Deploy hook (treat it as a credential — it deploys the service for anyone holding it), create the GitHub **environment** `production`, and store the URL there as the **environment secret** `RENDER_DEPLOY_HOOK_URL`. An environment secret, not a repository secret, is what keeps it unreachable from `checks.yml` and from fork pull requests (FR-028)
- [X] T030 [US3] Create `.github/workflows/deploy.yml` per [contracts/pipeline.md](./contracts/pipeline.md#deployyml--the-release): triggers `push` on `branches: [main]` plus `workflow_dispatch`; `permissions: contents: read`; `concurrency: {group: deploy-production, cancel-in-progress: true}` (a single group, so the newest commit wins — FR-024); job `checks` doing `uses: ./.github/workflows/checks.yml`; job `deploy` with `needs: checks` (FR-021), `timeout-minutes: 20`, `environment: {name: production, url: ${{ vars.PUBLIC_BASE_URL }}}`, whose steps are checkout → `scripts/render_deploy.sh "${{ github.sha }}"` with `RENDER_DEPLOY_HOOK_URL` from the environment secret → `scripts/wait_for_release.sh "${{ vars.PUBLIC_BASE_URL }}" "${{ github.sha }}"`. `pull_request_target` must appear nowhere (depends on T020, T027, T028, T029)
- [X] T031 [US3] Document the release and rollback procedure in `README.md` (FR-026): a merge to `main` publishes with no commands; to roll back, either run `scripts/render_deploy.sh <previous-good-sha>` followed by `scripts/wait_for_release.sh https://<host> <previous-good-sha>` with `RENDER_DEPLOY_HOOK_URL` exported, or use Render → Deploys → Rollback on the last successful deploy (faster — no rebuild); then revert the bad commit on `main` so the pipeline and the public address agree again (research [D11](./research.md#d11--rollback-fr-026))
- [X] T032 [US3] Validate [quickstart.md V9](./quickstart.md) (FR-020–FR-022, FR-025, SC-007): merge a trivial visible change, confirm Deploy starts by itself and the public address shows the change within 15 minutes with `/healthz` reporting the merged SHA and GitHub → Environments → production recording the deployment with its URL; confirm nobody ran a command or clicked anything in Render; then push a commit to a non-`main` branch and confirm nothing deploys
- [X] T033 [US3] Validate [quickstart.md V11](./quickstart.md) (FR-024): merge two pull requests within a minute of each other and confirm the earlier Deploy run is superseded rather than racing, that `/healthz` ends up reporting the **later** commit, and that no run reports success for a commit that is not the one serving
- [ ] T034 [US3] [MANUAL] Validate [quickstart.md V8](./quickstart.md) (SC-008, FR-023): note the current `commit` from `/healthz`; on a throwaway branch break the **image build only** and get it onto `main` deliberately (overriding the `image` check this one time); confirm the Deploy workflow fails, Render marks the deploy failed, and `/healthz` reports the **previous** commit throughout so visitors never see an error; then revert and confirm the next release is green

**Checkpoint**: Merges publish themselves, failures are loud, and the previous version always keeps
serving

---

## Phase 6: User Story 4 - The application runs the same way everywhere (Priority: P4)

**Goal**: A developer can build and start the same self-contained package the platform runs, from a
clean checkout with one documented command, configured entirely from the environment.

**Independent Test**: On a machine with only Docker installed, build and start the package from a
clean checkout and confirm the home page is served locally.

**Note**: the image itself is Phase 2 (T011) because US1, US2 and US3 all need it. This phase is
the story's remaining half — the documented contract and its verification.

### Implementation for User Story 4

- [X] T035 [US4] Document the packaged build and run in `README.md` (FR-008, FR-012, SC-010): `docker build --build-arg APP_COMMIT="$(git rev-parse HEAD)" -t student-competitions .`, `docker run --rm -p 8000:8000 student-competitions`, and the different-port form `docker run --rm -e PORT=9000 -p 9000:9000 student-competitions`
- [X] T036 [US4] Add the environment variable table to `README.md` (FR-012) reproducing all five rows of [contracts/container.md](./contracts/container.md#environment-variables) with purpose and default — `PORT` (entrypoint, default `8000`, set automatically by Render), `HOST` (entrypoint, default `0.0.0.0`, set in `render.yaml`), `APP_COMMIT` (read by `app/core/config.py`, default empty, build-arg stamp), `RENDER_GIT_COMMIT` (read by `app/core/config.py`, unset off-Render, set automatically by Render), `PYTHONUNBUFFERED` (Python, `1` in the image). State that none of them is secret and that no secret may be added to this table
- [X] T037 [US4] [MANUAL] Validate [quickstart.md V5](./quickstart.md) (FR-008–FR-011, SC-010): from a **clean checkout**, follow only the README commands and reach a visible home page in under 15 minutes; confirm `/healthz` reports the stamped commit; run again with `-e PORT=9000 -p 9000:9000` and confirm it listens there with no code change; run once with no `-e` flags at all and confirm it starts on the documented defaults; then `docker stop` the container and confirm it exits promptly with uvicorn shutting down gracefully in the logs — not a 10-second pause ending in a kill (this is what `exec` in the entrypoint buys)

**Checkpoint**: "Works on my machine" and "works in production" are the same statement, and the
README proves it

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Security verification and milestone acceptance

- [X] T038 Validate [quickstart.md V10](./quickstart.md) (FR-027, FR-028, SC-009): review the milestone's **full diff** for any hook URL, token or `.env` — the workflows must reference `secrets.RENDER_DEPLOY_HOOK_URL` and `vars.PUBLIC_BASE_URL` by name only; open a Deploy workflow log and confirm the hook URL never appears; confirm `.github/workflows/checks.yml` contains no `environment:` and no `secrets.` reference and that `pull_request_target` appears nowhere; confirm `.dockerignore` excludes `.git/`, `.venv/`, `tests/`, `specs/`, `docs/`, `.github/` and env files
- [X] T039 [P] [MANUAL] Enable GitHub secret scanning with push protection under Settings → Code security (free for public repositories) — a standing net under SC-009, recommended by [quickstart.md](./quickstart.md) B2
- [X] T040 [P] Update the "Repository layout" and "Tech stack" sections of `README.md` to include the new top-level files (`Dockerfile`, `.dockerignore`, `render.yaml`, `.github/workflows/`, `scripts/`) and the three infrastructure dependencies the milestone adds (Docker, GitHub Actions, Render)
- [X] T041 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` from the repository root one final time and confirm all three are green
- [ ] T042 Work through the **Milestone acceptance checklist** in [quickstart.md](./quickstart.md) and tick V1–V11 plus the README items; the milestone's stated criterion is "the page is accessible from outside, the pipeline is green"
- [ ] T043 [MANUAL] The day after the milestone lands, spot-check SC-003 (at least 99% of requests succeed over 24 hours) with a handful of requests to `https://<host>` plus Render's event log — there is no uptime monitor at this milestone and the spec places one in milestone 12

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3/US4
- **User Story 2 (Phase 4)**: Depends on Foundational. **Independent of US1** — the checks gate
  works whether or not anything is deployed
- **User Story 3 (Phase 5)**: Depends on Foundational, **US1** (the service and `PUBLIC_BASE_URL`
  must exist to deploy to and verify against) and **US2** (`deploy.yml` calls `checks.yml`)
- **User Story 4 (Phase 6)**: Depends on Foundational (T011). Independent of US1/US2/US3
- **Polish (Phase 7)**: Depends on all desired stories being complete

### User Story Dependencies

```text
Setup → Foundational ─┬─→ US1 (P1) ──┐
                      ├─→ US2 (P2) ──┼─→ US3 (P3) → Polish
                      └─→ US4 (P4) ──┘
```

US3 is the only story with cross-story dependencies, and they are inherent rather than
accidental: you cannot automate publishing to an address that does not exist yet, and publishing
without the gate is what FR-021 forbids.

### Within Each Phase

- **Phase 2**: tests (T004, T005) before implementation (T006–T009); T006 before T007; T009 after
  T007; T010 before T011; T011 before T012
- **Phase 3**: T013 before T014 (Render reads the Blueprint); T014 produces the hostname T015,
  T016, T017 and T018 all consume; T019 after T014
- **Phase 4**: T020 before T021 (`ci.yml` calls `checks.yml`); T021 before T023 (the check contexts
  only exist once a run has happened); T023 before T025 and T026 (there is no gate to prove
  without it)
- **Phase 5**: T027, T028, T029 before T030; T030 before T032, T033, T034
- **Phase 6**: T035 and T036 before T037 (V5 follows the README, so it must say something)

### Parallel Opportunities

- **Phase 1**: T002 and T003 together
- **Phase 2**: the two test modules T004 and T005 together; then T007 and T008 together
- **Phase 3–6**: once Foundational is done, **US1, US2 and US4 can be worked in parallel** by
  three people; US3 joins once US1 and US2 land
- **Phase 7**: T039 and T040 together

Most tasks within a story are sequential rather than parallel, because this milestone's files are
few and mostly chained (a workflow calls a script, a Blueprint produces a hostname). That is a
property of the work, not a missed opportunity.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Write both test modules together — different files, both failing until T006–T009:
Task: "Write tests/unit/test_config.py — COMMIT_SHA precedence and APP_VERSION vs pyproject.toml"
Task: "Write tests/integration/test_health.py — the GET /healthz contract"

# After T006, the router and the template anchoring are independent files:
Task: "Create app/routers/health.py"
Task: "Anchor the template directory in app/core/templates.py"
```

## Parallel Example: after the Foundational checkpoint

```bash
# Three independent tracks:
Developer A: US1 — render.yaml, Render bootstrap, public URL in the README, V1/V2/V3
Developer B: US2 — checks.yml, ci.yml, branch protection, V4/V6/V7
Developer C: US4 — README build/run commands and the environment variable table, V5
# Then, once A and B are done: US3 — the deploy scripts, deploy.yml, V8/V9/V11
```

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: Setup
2. Phase 2: Foundational — `/healthz`, its tests, the path anchoring and the image
3. Phase 3: User Story 1 — the Blueprint and the first public release
4. **STOP and VALIDATE**: open the public address from an outside device (T018)
5. At this point the milestone's headline result is real: the application is on the internet. The
   pipeline does not exist yet, and releases are Blueprint-driven

### Incremental Delivery

1. Setup + Foundational → the packaged application exists and is tested
2. **+ US1 → the public address serves the home page** (MVP, demonstrable to a stakeholder)
3. + US2 → broken code can no longer reach `main` (valuable even with manual releases)
4. + US3 → merges publish themselves and prove they landed
5. + US4 → the package's contract is documented and verified from a clean checkout
6. + Polish → secrets verified absent, acceptance checklist complete

Each increment stands on its own: stopping after step 3 leaves a deployed site with a working merge
gate and manual releases — a worse project than the finished milestone, but not a broken one.

### Parallel Team Strategy

With three developers: complete Setup + Foundational together (it is one short chain and splitting
it costs more than it saves), then take US1, US2 and US4 in parallel, and bring the team back
together for US3, which needs both US1's service and US2's reusable workflow.

---

## Notes

- **[MANUAL] tasks are not optional** — they are the dashboard bootstrap (T014, T015, T023, T029,
  T039) and the four acceptance procedures the plan's *Complexity Tracking* justifies as procedures
  rather than tests (T018, T025, T026, T034), plus V3 and V5 (T019, T037). Everything else is code
  or a command
- **Two values do not exist until T014 and T029 run**: the generated `onrender.com` hostname and the
  deploy hook URL. Tasks that consume them say so; do not guess either
- `[P]` tasks touch different files and depend on nothing unfinished
- `README.md` is edited by T016 (US1), T031 (US3), T035/T036 (US4) and T040 (Polish) — never in
  parallel with each other
- Commit after each task or logical group; every change reaches `main` through a pull request once
  T023 has been applied — including the changes that create the pipeline itself
- Stop at any checkpoint to validate the story independently
