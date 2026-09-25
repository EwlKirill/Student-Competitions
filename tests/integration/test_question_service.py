"""The question operations, row by row, on SQLite and on PostgreSQL.

Each test implements one row of the behaviour matrix in
specs/003-database-questions/contracts/question-service.md (rows 1–13) and runs once per engine
through the `session` fixture, so "works locally, differs in production" fails here (FR-030).
The clock is controlled by patching `app.services.questions.utc_now`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, func
from sqlmodel import Session, select

from app.models import Question
from app.schemas.question import (
    QUESTION_TEXT_MAX_LENGTH,
    REFERENCE_ANSWER_MAX_LENGTH,
    QuestionCreate,
    QuestionUpdate,
)
from app.services.questions import (
    QuestionNotFound,
    create_question,
    delete_question,
    get_question,
    list_questions,
    update_question,
)

MISSING_ID = 999_999


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], None]:
    """A controllable `utc_now`, starting well after the seeded samples; call it to advance."""
    now = [datetime(2100, 1, 1, 12, 0, tzinfo=UTC)]
    monkeypatch.setattr("app.services.questions.utc_now", lambda: now[0])

    def advance(by: timedelta) -> None:
        now[0] += by

    return advance


def create(session: Session, text: str = "Question?", answer: str = "Answer.") -> Question:
    return create_question(session, QuestionCreate(text=text, reference_answer=answer))


def count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Question)).one()


def test_created_question_can_be_read_back(session: Session) -> None:
    """Row 1 (US4-1)."""
    created = create(session, "What is 2 + 2?", "4")
    assert created.id is not None
    found = get_question(session, created.id)
    assert (found.text, found.reference_answer) == ("What is 2 + 2?", "4")


def test_ids_are_unique(session: Session) -> None:
    """Row 2 (FR-012)."""
    assert create(session).id != create(session).id


def test_list_is_ordered_by_creation_time_then_id(
    session: Session, clock: Callable[[timedelta], None]
) -> None:
    """Row 3 (US4-2, FR-016): two questions share a creation time; the id breaks the tie. The
    seeded samples, created earlier, come first."""
    samples = [question.id for question in list_questions(session)]
    first = create(session, "first")
    second = create(session, "second, same instant as first")
    clock(timedelta(seconds=1))
    third = create(session, "third")

    ids = [question.id for question in list_questions(session)]
    assert first.created_at == second.created_at
    assert ids == [*samples, first.id, second.id, third.id]
    assert [question.id for question in list_questions(session)] == ids


def test_update_changes_only_the_given_field_and_the_modified_time(
    session: Session, clock: Callable[[timedelta], None]
) -> None:
    """Row 4 (US4-3)."""
    question = create(session, "Old text", "Kept answer")
    created_at, updated_at = question.created_at, question.updated_at
    clock(timedelta(minutes=5))

    updated = update_question(session, question.id, QuestionUpdate(text="New text"))
    assert updated.text == "New text"
    assert updated.reference_answer == "Kept answer"
    assert updated.created_at == created_at
    assert updated.updated_at > updated_at


def test_deleted_question_is_gone(session: Session) -> None:
    """Row 5 (US4-4)."""
    question = create(session)
    delete_question(session, question.id)
    with pytest.raises(QuestionNotFound):
        get_question(session, question.id)
    assert question.id not in [q.id for q in list_questions(session)]


@pytest.mark.parametrize(
    "operation",
    [
        lambda session: get_question(session, MISSING_ID),
        lambda session: update_question(session, MISSING_ID, QuestionUpdate(text="x")),
        lambda session: delete_question(session, MISSING_ID),
    ],
    ids=["get", "update", "delete"],
)
def test_a_missing_id_raises_not_found(
    session: Session, operation: Callable[[Session], object]
) -> None:
    """Row 6 (US4-5, FR-015): an explicit outcome naming the id, and nothing changed."""
    before = count(session)
    with pytest.raises(QuestionNotFound, match=str(MISSING_ID)):
        operation(session)
    assert count(session) == before


def test_question_not_found_is_a_lookup_error() -> None:
    assert issubclass(QuestionNotFound, LookupError)
    assert QuestionNotFound(7).question_id == 7


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_invalid_input_never_reaches_the_database(session: Session, blank: str) -> None:
    """Row 7 (US4-6, FR-014): the schema refuses before any service call; nothing changes."""
    question = create(session, "Stored", "Stored answer")
    before = count(session)
    with pytest.raises(ValidationError):
        create_question(session, QuestionCreate(text=blank, reference_answer="x"))
    with pytest.raises(ValidationError):
        update_question(session, question.id, QuestionUpdate(reference_answer=blank))
    assert count(session) == before
    stored = get_question(session, question.id)
    assert (stored.text, stored.reference_answer) == ("Stored", "Stored answer")


def test_the_longest_allowed_values_round_trip(session: Session) -> None:
    """Row 9 (FR-014, FR-017): also proves PostgreSQL's VARCHAR counts characters, not bytes."""
    text = "я" * QUESTION_TEXT_MAX_LENGTH
    answer = "я" * REFERENCE_ANSWER_MAX_LENGTH
    found = get_question(session, create(session, text, answer).id)
    assert (found.text, found.reference_answer) == (text, answer)


def test_surrounding_whitespace_is_stripped_and_the_line_break_kept(session: Session) -> None:
    """Row 10 (FR-014, FR-017)."""
    found = get_question(session, create(session, "  Line one\nLine two  ").id)
    assert found.text == "Line one\nLine two"


def test_markup_is_stored_exactly(session: Session) -> None:
    """Row 11 (FR-017): stored as given; escaping is the template's job."""
    found = get_question(session, create(session, "<b>bold</b> & more").id)
    assert found.text == "<b>bold</b> & more"


def test_timestamps_read_back_as_utc(session: Session, engine: Engine) -> None:
    """Row 13 (FR-006): timezone-aware UTC from a fresh session, on both engines."""
    question_id = create(session).id
    with Session(engine) as fresh:
        found = get_question(fresh, question_id)
        for stamp in (found.created_at, found.updated_at):
            assert stamp.tzinfo is not None
            assert stamp.utcoffset() == timedelta(0)
