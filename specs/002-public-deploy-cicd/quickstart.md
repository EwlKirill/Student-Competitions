# Quickstart & Validation: Public Deployment & CI/CD (Milestone 2)

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](./plan.md)

How to stand the deployment up, how to run the packaged application, and how to prove the
milestone is done. Every validation scenario maps to an acceptance scenario or success criterion
in [spec.md](./spec.md). The run-and-configure parts belong in the README as well (FR-007, FR-012).

The milestone's stated criterion is **"the page is accessible from outside, the pipeline is
green."**

## Prerequisites

| Need | For |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | Running the app and the suite locally (unchanged from milestone 1) |
| Docker (Desktop or Engine) | Building and running the packaged image |
| A Render account with the GitHub repository connected | Creating the service |
| Admin rights on the GitHub repository | Secrets, environments, branch protection |
| `gh` (optional) | The scripted branch-protection rule; the dashboard steps are given too |

No `.env` file, no API key and no database — the published application needs none (FR-030).

---

## One-time bootstrap

Everything except these three steps is in the repository. Do them once, in order.

### B1 — Create the service from the Blueprint

1. Merge this milestone's branch (or push it) so `render.yaml` exists on the branch Render will
   read.
2. In Render: **New → Blueprint** → this repository → branch `main` → file `render.yaml`.
3. Review the plan Render shows (one free `web` service, region `frankfurt`, Docker runtime) and
   deploy the Blueprint.
4. **Record the hostname Render generated.** It is usually `student-competitions.onrender.com`,
   but Render appends a suffix if the name is taken — the real value is what matters.

The service's configuration now comes from `render.yaml`. Blueprint **Auto-Sync stays on**: a
merged change to that file is applied automatically. Code deploys stay off
(`autoDeployTrigger: "off"`), so only the pipeline releases.

### B2 — Wire the deploy hook into GitHub

1. Render → the service → **Settings → Deploy hook** → copy the URL. Treat it as a credential: it
   deploys the service for anyone who has it.
2. GitHub → **Settings → Environments → New environment** → `production`.
3. In that environment, add the **secret** `RENDER_DEPLOY_HOOK_URL` = the copied URL.
4. GitHub → **Settings → Secrets and variables → Actions → Variables** → add the repository
   **variable** `PUBLIC_BASE_URL` = `https://<the hostname from B1>` (no trailing slash).
5. Put the same public address in the README (FR-007).

Recommended while you are here: **Settings → Code security** → enable secret scanning and push
protection (free for public repositories). It is a standing net under SC-009.

### B3 — Protect `main`

```bash
./scripts/setup_branch_protection.sh          # requires `gh auth login` first
```

Or by hand: **Settings → Branches → Add branch protection rule** for `main` → require a pull
request before merging (0 approvals) → require status checks to pass → select **`checks / quality`**
and **`checks / image`** → require branches to be up to date → block force pushes and deletions.

> The status check names only appear in that picker **after** the workflows have run at least
> once. If the list is empty, open a throwaway pull request first, let it run, then come back.

> **Free-plan constraint**: branch protection and rulesets are free for public repositories; a
> private repository on a free GitHub plan cannot enforce them, and FR-016 then cannot be met
> without making the repository public or upgrading the plan. There is no implementation-side
> workaround.

---

## Running the packaged application locally

```bash
# Build (stamping the commit, exactly as CI does)
docker build --build-arg APP_COMMIT="$(git rev-parse HEAD)" -t student-competitions .

# Run with documented defaults
docker run --rm -p 8000:8000 student-competitions
```

Open <http://localhost:8000>. `curl -s http://localhost:8000/healthz` returns
`{"status":"ok","version":"0.1.0","commit":"<sha>"}`.

A different port, supplied entirely from outside (US4 scenario 2):

```bash
docker run --rm -e PORT=9000 -p 9000:9000 student-competitions
```

Full image and environment contract: [contracts/container.md](./contracts/container.md).

## Releasing, and releasing backwards

A release needs no commands — merge to `main` and watch the **Deploy** workflow. The same actions
are available by hand, which is what makes the rollback procedure (FR-026) short:

```bash
export RENDER_DEPLOY_HOOK_URL='…'                    # from B2; never commit it
./scripts/render_deploy.sh <commit-sha>              # deploy that exact commit
./scripts/wait_for_release.sh https://<host> <sha>   # wait until it is actually serving
```

To roll back: run the two commands above with the **previous good SHA**, or use Render →
**Deploys → Rollback** on the last successful deploy (faster — no rebuild). Then revert the bad
commit on `main` in the normal way, so the pipeline and the public address agree again.

---

## Validation scenarios

### V1 — The application is reachable from outside (US1 scenario 1; FR-001, FR-003; SC-001) — *manual, required once*

1. From a device that has never run the project, on a different network (a phone on mobile data),
   open `https://<host>`.
2. **Expected**: the milestone 1 home page, styled, with the application name and description
   (FR-002), over HTTPS with a valid certificate and no warning.
3. Time a reload while the service is warm. **Expected**: under 3 seconds (SC-002). A first load
   after 15 idle minutes takes about a minute — that is the free tier spinning up and is
   explicitly excluded from SC-002.

### V2 — The public surface behaves (US1 scenarios 2 and 4; FR-003, FR-004, FR-005)

```bash
HOST_URL=https://<host>
curl -sI  http://<host>            | head -1     # → 301/308 to https (FR-003)
curl -s -o /dev/null -w '%{http_code}\n' "$HOST_URL"            # → 200
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' "$HOST_URL/about"   # → 404 text/html
curl -s "$HOST_URL/healthz"                                      # → {"status":"ok",…}
```

**Expected**: the 404 is the application's own friendly page — open it in a browser to confirm it
is the project's error page with a link home, not a Render error page and not a stack trace
(FR-004, FR-029).

### V3 — Restart restores service by itself (US1 scenario 3; FR-006; SC-011) — *manual, required once*

1. Render → the service → **Manual Restart** (or trigger a redeploy).
2. Poll `curl -s "$HOST_URL/healthz"` until it answers again.
3. **Expected**: the service comes back on its own, `status: "ok"`, same `commit`. Nobody
   intervened.

### V4 — Pull requests are verified automatically (US2 scenarios 1 and 5; FR-013…FR-015, FR-017; SC-006)

1. Open a pull request against `main`.
2. **Expected**: `checks / quality` and `checks / image` appear and run without anyone asking,
   finishing within 5 minutes; push another commit and both re-run (FR-015).
3. Open a failing run's log. **Expected**: the failure names the test, or the file and the ruff
   rule — enough to fix it without reproducing locally (FR-017).

### V5 — The packaged application runs identically (US4; FR-008…FR-011; SC-010) — *manual, required once*

1. From a clean checkout, run the two Docker commands under **Running the packaged application
   locally**. **Expected**: from checkout to a visible home page in under 15 minutes.
2. Confirm `/healthz` reports the stamped commit; run again with `-e PORT=9000` and confirm it
   listens there with no code change.
3. `docker stop` the container. **Expected**: it exits promptly and the logs show uvicorn shutting
   down gracefully — not a 10-second pause ending in a kill (this is what `exec` in the entrypoint
   is for).
4. **Expected**: the README documents the build command, the run command, the public address and
   every variable in [contracts/container.md](./contracts/container.md) (FR-007, FR-012).

### V6 — A failing test blocks the merge (US2 scenarios 2 and 4; FR-016; SC-004) — *manual, required once*

1. On a throwaway branch, add a test that asserts something false. Open a pull request.
2. **Expected**: `checks / quality` fails, the pull request is reported failing, and **the merge
   button is disabled** — reported-but-mergeable is a failure of this check, and means branch
   protection is not configured (B3).
3. Remove the failing test. **Expected**: the checks turn green and merging becomes possible.
4. Close the pull request without merging.

### V7 — A style violation blocks the merge (US2 scenario 3; FR-014, FR-016; SC-005) — *manual, required once*

1. On a throwaway branch, introduce a deliberate formatting or lint violation (an unused import,
   or misformatted code). Open a pull request.
2. **Expected**: `checks / quality` fails at `ruff check` or `ruff format --check`, naming the file
   and rule, and the merge is blocked.
3. Close the pull request without merging.

### V8 — A broken publish does not take the site down (US3 scenario 3; FR-023; SC-008) — *manual, required once*

1. Note the current `commit` from `/healthz`.
2. On a throwaway branch, break the **image build only** — e.g. a `Dockerfile` line that cannot
   run. Get it onto `main` deliberately (the `image` check will resist; this is the one time you
   override it, and it is why the branch is throwaway).
3. **Expected**: the Deploy workflow fails, Render marks the deploy failed, and
   `curl "$HOST_URL/healthz"` still reports the **previous** commit throughout. Visitors never see
   an error.
4. Revert, and confirm the next release restores a green pipeline.

### V9 — A merge reaches the public address on its own (US3 scenarios 1, 2 and 5; FR-020, FR-021; SC-007)

1. Make a trivial visible change (a word in the home page description), open a pull request, let
   the checks pass, merge it.
2. **Expected**: the Deploy workflow starts by itself; it runs the checks, calls the hook and then
   waits; within 15 minutes the public address shows the change, `/healthz` reports the merged
   SHA, and the GitHub **Environments → production** view records the deployment with its URL
   (FR-025).
3. **Expected**: nobody ran a command or clicked anything in Render (FR-020).
4. Push a commit to a non-`main` branch. **Expected**: nothing deploys (FR-022).

### V10 — Nothing secret is in the repository (FR-027, FR-028; SC-009)

1. Review the milestone's full diff. **Expected**: no hook URL, no token, no `.env`; the workflows
   reference `secrets.RENDER_DEPLOY_HOOK_URL` and `vars.PUBLIC_BASE_URL` by name only.
2. Open a Deploy workflow log. **Expected**: the hook URL never appears — the script prints the
   response status, not what it called.
3. **Expected**: `checks.yml` contains no `environment:` and no `secrets.` reference, so a fork
   pull request can reach no credential (FR-028); `pull_request_target` appears nowhere.
4. Confirm the built image carries nothing extra: `.dockerignore` excludes `.git/`, `.venv/`,
   `tests/`, `specs/`, `docs/`, `.github/` and env files.

### V11 — Two merges in quick succession (edge case; FR-024)

1. Merge two pull requests within a minute of each other.
2. **Expected**: the earlier Deploy run is superseded (cancelled) rather than racing; the public
   `/healthz` ends up reporting the **later** commit; no run reports success for a commit that is
   not the one serving.

---

## Milestone acceptance checklist

- [ ] V1 — the page opens from an outside device over HTTPS (SC-001, SC-002)
- [X] V2 — HTTP redirects, `/healthz` answers, unknown paths give the app's own 404
- [ ] V3 — a restart restores service unattended (SC-011)
- [X] V4 — pull requests are checked automatically within 5 minutes (SC-006)
- [X] V5 — the image builds and runs from a clean checkout in under 15 minutes (SC-010)
- [X] V6 — a failing test blocks the merge (SC-004)
- [X] V7 — a style violation blocks the merge (SC-005)
- [ ] V8 — a broken publish leaves the previous version serving (SC-008)
- [X] V9 — a merge reaches the public address with zero manual steps (SC-007)
- [X] V10 — the diff and the logs contain no secret (SC-009)
- [ ] V11 — the newest commit wins a race (FR-024)
- [X] The README records the public address and every environment variable (FR-007, FR-012)
- [X] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` are green locally
- [ ] SC-003 (99% of requests succeed over 24 h) — checked the day after the milestone lands, by
      a handful of spot requests plus Render's event log; there is no uptime monitor at this
      milestone and the spec puts one in milestone 12

## Reference

- HTTP surface: [contracts/http-routes.md](./contracts/http-routes.md)
- Image, entrypoint, environment: [contracts/container.md](./contracts/container.md)
- Render service: [contracts/render-service.md](./contracts/render-service.md)
- Workflows, secrets, branch protection: [contracts/pipeline.md](./contracts/pipeline.md)
- Configuration and the health payload: [data-model.md](./data-model.md)
- Decisions and rejected alternatives: [research.md](./research.md)
