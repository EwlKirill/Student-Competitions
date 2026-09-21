"""HTTP contract for the home page and the friendly not-found page.

See specs/001-hello-world-page/contracts/http-routes.md.
"""

import re

from fastapi.testclient import TestClient

from app.core.config import APP_NAME

VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def test_app_name_is_non_empty() -> None:
    """Guard the containment assertion below from passing vacuously."""
    assert APP_NAME


def test_home_returns_ok(client: TestClient) -> None:
    assert client.get("/").status_code == 200


def test_home_is_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_home_shows_the_application_name(client: TestClient) -> None:
    assert APP_NAME in client.get("/").text


def test_home_headline_is_the_application_name(client: TestClient) -> None:
    """Asserted against the <h1>, not the whole body: the shared layout and the error page also
    carry APP_NAME, so a body-wide check alone cannot tell the home page from a 404."""
    match = re.search(r"<h1>(.*?)</h1>", client.get("/").text, re.DOTALL)
    assert match is not None, "the home page has no <h1>"
    assert APP_NAME in match.group(1)


def test_home_has_a_non_empty_title(client: TestClient) -> None:
    match = re.search(r"<title>(.*?)</title>", client.get("/").text, re.DOTALL)
    assert match is not None, "the page has no <title>"
    assert match.group(1).strip()


def test_home_head_carries_the_viewport_meta(client: TestClient) -> None:
    head = re.search(r"<head>(.*?)</head>", client.get("/").text, re.DOTALL)
    assert head is not None, "the page has no <head>"
    assert VIEWPORT_META in head.group(1)


def test_unknown_path_returns_a_rendered_not_found_page(client: TestClient) -> None:
    response = client.get("/about")
    assert response.status_code == 404
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<html" in response.text
