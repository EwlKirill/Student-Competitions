"""HTTP contract for the home page and the friendly not-found page.

See specs/001-hello-world-page/contracts/http-routes.md and, for the question list,
specs/003-database-questions/contracts/http-routes.md#get---home-page. Every test that uses
`client` runs once per database engine.
"""

import re
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, delete

import app.routers.pages as pages
from app.core.config import APP_NAME, APP_VERSION, COMMIT_SHA
from app.core.migrations import head_revision
from app.core.templates import SHORT_COMMIT_LENGTH
from app.models import Question
from app.schemas.question import QuestionCreate
from app.services.questions import create_question

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


def _footer(body: str) -> str:
    match = re.search(r"<footer.*?</footer>", body, re.DOTALL)
    assert match is not None, "the page has no <footer>"
    return match.group(0)


def test_home_footer_reports_the_release(client: TestClient) -> None:
    """The version and the commit are on the page itself, so which release is serving is visible
    without calling /healthz (FR-025)."""
    footer = _footer(client.get("/").text)
    assert f"v{APP_VERSION}" in footer
    assert COMMIT_SHA[:SHORT_COMMIT_LENGTH] in footer


def test_home_footer_carries_the_full_commit(client: TestClient) -> None:
    """The short form is what is read; the full value stays available on hover."""
    assert f'title="{COMMIT_SHA}"' in _footer(client.get("/").text)


def test_error_page_reports_the_release_too(client: TestClient) -> None:
    """The footer lives in the shared layout, so every page inherits it — including this one,
    which is rendered by an exception handler rather than by a router."""
    footer = _footer(client.get("/about").text)
    assert f"v{APP_VERSION}" in footer
    assert COMMIT_SHA[:SHORT_COMMIT_LENGTH] in footer


# ---------------------------------------------------------------------------------------------
# The question list (milestone 3)
# ---------------------------------------------------------------------------------------------

UNAVAILABLE_NOTICE = (
    '<p class="data-unavailable" role="status">Question data is temporarily unavailable. '
    "Please try again in a moment.</p>"
)


def _question_items(body: str) -> list[str]:
    """The raw (still escaped) contents of each `<li>` in the question list."""
    lists = re.findall(r'<ol class="question-list">(.*?)</ol>', body, re.DOTALL)
    assert len(lists) == 1, f"expected one question list, found {len(lists)}"
    return re.findall(r"<li>(.*?)</li>", lists[0], re.DOTALL)


def _fail_database_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, "list_questions", failing)


def test_home_has_the_questions_section(client: TestClient) -> None:
    body = client.get("/").text
    assert '<section id="questions" aria-labelledby="questions-heading">' in body
    assert '<h2 id="questions-heading">Sample questions</h2>' in body


def test_home_lists_the_sample_questions_once_each_in_order(
    client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    """Compared with `markupsafe.escape`, which is what Jinja uses (`"` becomes `&#34;`)."""
    expected = [str(escape(sample["text"])) for sample in sample_questions]
    assert _question_items(client.get("/").text) == expected


def test_home_keeps_the_line_break_inside_the_ukrainian_sample(
    client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    multiline = [sample["text"] for sample in sample_questions if "\n" in sample["text"]]
    assert multiline, "the samples should include a multi-line question"
    assert all(text in _question_items(client.get("/").text) for text in multiline)


def test_home_never_shows_a_reference_answer(
    client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    body = client.get("/").text
    for sample in sample_questions:
        answer = sample["reference_answer"]
        assert answer not in body
        assert str(escape(answer)) not in body


def test_home_has_no_write_affordance(client: TestClient) -> None:
    """No form, no button, and no link out of a list item (US1-2, FR-018)."""
    body = client.get("/").text
    assert "<form" not in body
    assert "<button" not in body
    assert all("<a" not in item for item in _question_items(body))


def test_question_text_is_escaped(client: TestClient, session: Session) -> None:
    session.add(Question(text="<b>bold</b> & more", reference_answer="x"))
    session.commit()
    body = client.get("/").text
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; more" in body
    assert "<b>bold</b>" not in body


def test_home_shows_an_empty_state_when_there_are_no_questions(
    client: TestClient, session: Session
) -> None:
    session.exec(delete(Question))
    session.commit()
    body = client.get("/").text
    assert '<p class="questions-empty">No questions yet.</p>' in body
    assert '<ol class="question-list">' not in body


def test_home_shows_the_same_list_on_every_load(client: TestClient) -> None:
    lists = [_question_items(client.get("/").text) for _ in range(3)]
    assert lists[0] == lists[1] == lists[2]


def test_home_degrades_when_the_database_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database blip still renders the page, with a notice and no error detail (FR-026)."""
    _fail_database_reads(monkeypatch)
    response = client.get("/")
    body = response.text
    assert response.status_code == 200
    assert re.search(r"<h1>.*?</h1>", body, re.DOTALL)
    assert "<footer" in body
    assert UNAVAILABLE_NOTICE in body
    assert "question-list" not in body
    for detail in ("OperationalError", "boom", "SELECT"):
        assert detail not in body


# ---------------------------------------------------------------------------------------------
# The database status line (milestone 3)
# ---------------------------------------------------------------------------------------------

DISPLAY_NAMES = {"sqlite": "SQLite", "postgresql": "PostgreSQL"}


def _status_line(body: str) -> re.Match[str]:
    matches = list(re.finditer(r'<p class="db-status"(.*?)>(.*?)</p>', body, re.DOTALL))
    assert len(matches) == 1, f"expected one status line, found {len(matches)}"
    return matches[0]


def test_status_line_carries_the_machine_readable_attributes(
    client: TestClient, request: pytest.FixtureRequest
) -> None:
    engine = request.node.callspec.params["database_url"]
    attributes = _status_line(client.get("/").text).group(1)
    assert f'data-engine="{engine}"' in attributes
    assert f'data-revision="{head_revision()}"' in attributes
    assert 'data-boots="1"' in attributes


def test_status_line_reads_as_text(client: TestClient, request: pytest.FixtureRequest) -> None:
    engine = request.node.callspec.params["database_url"]
    text = _status_line(client.get("/").text).group(2)
    assert text == (
        f"Database: {DISPLAY_NAMES[engine]} · schema revision <code>{head_revision()}</code>"
        " · boot #1"
    )


def test_status_line_sits_between_the_questions_and_the_footer(client: TestClient) -> None:
    body = client.get("/").text
    status = _status_line(body).start()
    assert body.index('<section id="questions"') < status < body.index("<footer")


@pytest.mark.parametrize("failing_read", ["list_questions", "read_database_status"])
def test_a_failing_read_replaces_both_the_list_and_the_status_line(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failing_read: str
) -> None:
    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, failing_read, failing)
    body = client.get("/").text
    assert UNAVAILABLE_NOTICE in body
    assert "question-list" not in body
    assert "db-status" not in body


def test_home_lists_500_questions_quickly(
    client: TestClient, session: Session, sample_questions: list[dict[str, str]]
) -> None:
    """SC-005: the page stays fast with a realistic bank, samples first, then creation order."""
    for i in range(500):
        create_question(
            session, QuestionCreate(text=f"Question {i:03d}", reference_answer="Answer.")
        )

    started = time.perf_counter()
    response = client.get("/")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 3, f"GET / took {elapsed:.2f}s with 506 questions"
    items = _question_items(response.text)
    assert len(items) == 506
    assert items[:6] == [str(escape(sample["text"])) for sample in sample_questions]
    assert items[6:] == [f"Question {i:03d}" for i in range(500)]
