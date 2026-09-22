# HTTP Contract: Public Deployment & CI/CD (Milestone 2)

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](../plan.md)

This milestone changes the HTTP surface in exactly one way: it adds `GET /healthz`. Everything
else — the home page, the static mount, the friendly not-found page — is inherited **unchanged**
from [milestone 1's contract](../../001-hello-world-page/contracts/http-routes.md), which stays
authoritative for those routes (FR-002).

What *does* change for every route is where they are served from and over what: the public base
address becomes `https://<service-name>.onrender.com` (recorded in the README per FR-007 and in
the `PUBLIC_BASE_URL` repository variable), and TLS plus the HTTP→HTTPS redirect are provided by
Render's edge, not by the application (FR-003, research D8).

---

## `GET /healthz` — service status

**Purpose**: one address that reports both liveness and the running version (FR-005), serving
three consumers: Render's health check (`healthCheckPath`), the deploy pipeline's post-release
verification (research D15), and a human answering "what is live right now?" (FR-025).

**Request**: no parameters, no headers required, no cookies read, no authentication.

**Response `200 OK`**

| Aspect | Contract |
|---|---|
| `Content-Type` | `application/json` |
| Body | `{"status": "ok", "version": "<APP_VERSION>", "commit": "<COMMIT_SHA>"}` — exactly these three keys |
| `status` | The literal string `"ok"` |
| `version` | `app.core.config.APP_VERSION`; equals `project.version` in `pyproject.toml` |
| `commit` | `app.core.config.COMMIT_SHA` — 40 lowercase hex characters on a deployed instance, the literal `"unknown"` on an unstamped local run. Never empty. |
| Side effects | None. No I/O of any kind: no database, no file read, no outbound request |
| Latency | Must answer well inside Render's **5-second** health-check timeout; the handler allocates one dict |
| Caching | Must not be cached: no `Cache-Control` is set by the app, and consumers append a cache-busting behaviour by polling a changing value (the commit) |

**Errors**: none by design. The route has no input to reject and no dependency to fail; if it
cannot answer, the process is not running, which is precisely the signal the endpoint exists to
give.

**Why JSON and not a rendered page**: the audience is Render's health checker and a shell script.
Principle II's ban on JSON applies to the *user interface* — this endpoint has no template, no
client-side code and no human-facing markup (research D7). It is the only non-HTML response in the
application.

**Handler**: `app/routers/health.py`, registered in `app/main.py` alongside the pages router.
Values come from `app/core/config.py` — see [data-model.md](../data-model.md#1-configuration-read-from-the-environment).

**Consumers and what each asserts**:

| Consumer | Assertion |
|---|---|
| Render health check | 2xx within 5 s, repeatedly; 60 s of consecutive failures restarts the instance, and a new instance that never passes cancels the deploy (FR-006, FR-023) |
| `scripts/wait_for_release.sh` | `.commit == <deployed sha>` before the deploy job may succeed (SC-007, FR-024) |
| CI `image` job | `200` with `.status == "ok"` from the freshly built container (FR-011) |
| `tests/integration/test_health.py` | Status, content type, the three keys, `version == APP_VERSION`, `commit` non-empty |

---

## Inherited routes — what this milestone must not change

| Route | Contract | Verified here by |
|---|---|---|
| `GET /` | Milestone 1, unchanged: `200`, `text/html; charset=utf-8`, server-rendered, app name in `<h1>` and `<title>` (FR-002) | The existing suite, the CI container smoke test, and quickstart V2 against the public address |
| `GET /static/{path}` | Milestone 1, unchanged; files are baked into the image and served from the package directory (research D14) | Quickstart V2 (the page renders styled over the public address) |
| Any unmatched path | Milestone 1, unchanged: the application's own friendly HTML error page with the original status code — **not** a Render error page (FR-004) | `tests/integration/test_home.py`, and quickstart V4 against the public address |

**FR-029 (no internal error details to users)** is inherited: `app/main.py`'s `HTTPException`
handler renders `pages/error.html` for every HTTP error, and FastAPI is run without debug mode, so
an unhandled exception yields a bare `500` with no traceback in the body. Tracebacks go to
Render's log stream, where the team can see them and visitors cannot.

---

## Routes deliberately still absent

| Not implemented | Arrives in |
|---|---|
| A separate readiness endpoint, or dependency checks inside `/healthz` | When there is a dependency to check — milestone 3's database |
| A metrics endpoint | Milestone 12 (observability is explicitly out of scope here) |
| HTMX partial endpoints | The first interactive feature |
| Auth routes | Milestone 4 |
| Any other JSON API | Not planned — the UI is server-rendered (Principle II) |
