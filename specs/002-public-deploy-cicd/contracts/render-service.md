# Render Service Contract: `render.yaml`

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](../plan.md)

The hosting side of the milestone, as code. Rationale for every value:
[research.md D1](../research.md#d1--hosting-platform-and-plan),
[D2](../research.md#d2--what-triggers-a-deploy-github-actions-calling-a-render-deploy-hook),
[D3](../research.md#d3--infrastructure-as-code-renderyaml-blueprint).

## The Blueprint

`render.yaml`, at the repository root, declaring one web service:

```yaml
services:
  - type: web
    name: student-competitions
    runtime: docker
    plan: free
    region: frankfurt
    branch: main
    dockerfilePath: ./Dockerfile
    dockerContext: .
    healthCheckPath: /healthz
    autoDeployTrigger: "off"
    envVars:
      - key: HOST
        value: 0.0.0.0
```

| Field | Value | Why, and what breaks otherwise |
|---|---|---|
| `type` | `web` | The only service this milestone has. |
| `name` | `student-competitions` | Determines the `onrender.com` hostname and therefore the public address (FR-001). Render appends a suffix if the name is taken, so the **actual** hostname is read back after creation and recorded in the README (FR-007) and in `PUBLIC_BASE_URL`. |
| `runtime` | `docker` | Builds [the project's Dockerfile](./container.md) rather than a Render buildpack, so the published unit is the one a developer can run (FR-011). |
| `plan` | `free` | As specified by the user. Consequences (spin-down, single instance) are accepted in the spec's assumptions. |
| `region` | `frankfurt` | Closest of Render's regions to the team (SC-002). **Immutable after creation** — a different region means a new service and a new URL. |
| `branch` | `main` | The only branch Render will ever build; combined with `autoDeployTrigger: "off"`, it also means a push to any other branch can publish nothing (FR-022). |
| `dockerfilePath` / `dockerContext` | `./Dockerfile`, `.` | Explicit rather than defaulted, so the file says where the image comes from. |
| `healthCheckPath` | `/healthz` | Traffic is only switched to a new instance once this returns 2xx, and 60 s of consecutive failures restarts the instance (FR-006, FR-023). |
| `autoDeployTrigger` | `"off"` — **quoted** | The pipeline is the only thing that deploys (FR-020, FR-021). YAML 1.1 would parse a bare `off` as `false`; the quotes are load-bearing. |
| `envVars` | `HOST=0.0.0.0` | `PORT` is supplied by Render; `RENDER_GIT_COMMIT` is automatic. No secret is declared here, and none may be added — the service needs none (FR-030). |

## What the Blueprint does not cover

Three bootstrap actions are interactive by design; they happen once, and
[quickstart.md](../quickstart.md) is their record.

| Step | Produces |
|---|---|
| Create the Render workspace and grant access to the GitHub repository | Render can read the repo and run builds |
| **New → Blueprint**, pointing at this repository, branch `main`, file `render.yaml` | The service, and its `onrender.com` hostname |
| Copy the service's deploy hook URL from **Settings → Deploy hook** | The value stored as the `RENDER_DEPLOY_HOOK_URL` environment secret |

After that, `render.yaml` is the configuration: Blueprint Auto-Sync stays **on**, so a merged
change to the file becomes live settings without anyone opening the dashboard.

## Behavioural contract

| Situation | Required outcome | Mechanism |
|---|---|---|
| Push to `main` | Nothing deploys until the pipeline says so | `autoDeployTrigger: "off"` (FR-020, FR-021) |
| Push to any other branch | Nothing deploys, ever | `branch: main` **and** auto-deploy off (FR-022) |
| Deploy hook called with `ref=<sha>` | That exact commit is built and deployed | Deploy hook `ref` parameter |
| Build fails | Previous version keeps serving; deploy marked failed | Render cancels the deploy on build failure (FR-023, SC-008) |
| New instance never passes `/healthz` | Deploy cancelled after Render's 15-minute window; previous version keeps serving | `healthCheckPath` (FR-023) |
| Instance crashes or the platform restarts it | Restarted automatically, service resumes | Render's supervision (FR-006, SC-011) |
| A request arrives over plain HTTP | Redirected to HTTPS at the edge | Render's managed TLS (FR-003) |
| `render.yaml` changes on `main` | Settings applied automatically; Render redeploys affected services | Blueprint Auto-Sync (expected, and noted in the quickstart so a doubled deploy is not mistaken for a fault) |
| 15 minutes without traffic | Service spins down; next request cold-starts in ~1 minute | Free instance type (accepted by the spec) |

## Rollback surface

Two documented paths (FR-026), both in [quickstart.md](../quickstart.md):

1. **Re-deploy a known-good commit** — `scripts/render_deploy.sh <previous-sha>` followed by
   `scripts/wait_for_release.sh`. Same mechanism as a release, so it is exercised constantly.
2. **Render dashboard → Deploys → Rollback** on the last successful deploy. Faster (no rebuild),
   and available to anyone with dashboard access and no terminal.

The durable fix is always to revert the commit on `main` and let the pipeline publish the revert;
the two paths above are for getting the public address healthy first.
