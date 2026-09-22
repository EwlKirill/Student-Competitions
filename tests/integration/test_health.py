"""HTTP contract for the service status endpoint.

See specs/002-public-deploy-cicd/contracts/http-routes.md#get-healthz--service-status.
"""

from fastapi.testclient import TestClient

from app.core.config import APP_VERSION


def test_healthz_returns_ok(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_healthz_is_json(client: TestClient) -> None:
    """Render's health checker and a shell script are the audience — not a browser."""
    response = client.get("/healthz")
    assert response.headers["content-type"] == "application/json"


def test_healthz_has_exactly_the_three_documented_keys(client: TestClient) -> None:
    """Exactly three: anything varying per request would leak infrastructure detail on an
    unauthenticated endpoint and make the payload unstable to assert against."""
    assert set(client.get("/healthz").json()) == {"status", "version", "commit"}


def test_healthz_status_is_ok(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"


def test_healthz_reports_the_application_version(client: TestClient) -> None:
    assert client.get("/healthz").json()["version"] == APP_VERSION


def test_healthz_commit_is_a_non_empty_string(client: TestClient) -> None:
    """`"unknown"` on an unstamped local run, a 40-character SHA once deployed — never empty."""
    commit = client.get("/healthz").json()["commit"]
    assert isinstance(commit, str)
    assert commit
