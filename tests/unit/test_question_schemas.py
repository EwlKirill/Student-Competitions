"""The validation boundary for question writes.

See specs/003-database-questions/data-model.md (§1 validation rules, §3 schemas) and the
behaviour matrix in contracts/question-service.md, rows 7, 8, 10 and 12. Cyrillic `я` is used
for the length limits because it is two bytes in UTF-8: the limits count characters, not bytes.
"""

import pytest
from pydantic import ValidationError

from app.schemas.question import (
    QUESTION_TEXT_MAX_LENGTH,
    REFERENCE_ANSWER_MAX_LENGTH,
    QuestionCreate,
    QuestionUpdate,
)

BLANKS = ["", "   ", "\n\t"]


@pytest.mark.parametrize("blank", BLANKS, ids=["empty", "spaces", "newline-tab"])
@pytest.mark.parametrize("field", ["text", "reference_answer"])
def test_create_rejects_a_blank_field(field: str, blank: str) -> None:
    data = {"text": "Question?", "reference_answer": "Answer.", field: blank}
    with pytest.raises(ValidationError):
        QuestionCreate(**data)


@pytest.mark.parametrize("missing", ["text", "reference_answer"])
def test_create_requires_both_fields(missing: str) -> None:
    data = {"text": "Question?", "reference_answer": "Answer."}
    del data[missing]
    with pytest.raises(ValidationError):
        QuestionCreate(**data)


@pytest.mark.parametrize(
    ("field", "limit"),
    [("text", QUESTION_TEXT_MAX_LENGTH), ("reference_answer", REFERENCE_ANSWER_MAX_LENGTH)],
)
def test_create_rejects_one_character_over_the_limit(field: str, limit: int) -> None:
    data = {"text": "Question?", "reference_answer": "Answer.", field: "я" * (limit + 1)}
    with pytest.raises(ValidationError):
        QuestionCreate(**data)


@pytest.mark.parametrize(
    ("field", "limit"),
    [("text", QUESTION_TEXT_MAX_LENGTH), ("reference_answer", REFERENCE_ANSWER_MAX_LENGTH)],
)
def test_create_accepts_exactly_the_limit_after_stripping(field: str, limit: int) -> None:
    """Surrounding whitespace is stripped before the length is checked."""
    data = {"text": "Question?", "reference_answer": "Answer.", field: f"  {'я' * limit}  "}
    assert getattr(QuestionCreate(**data), field) == "я" * limit


def test_limits_match_the_specification() -> None:
    assert QUESTION_TEXT_MAX_LENGTH == 1000
    assert REFERENCE_ANSWER_MAX_LENGTH == 5000


def test_surrounding_whitespace_is_stripped_and_internal_breaks_kept() -> None:
    created = QuestionCreate(text="  Line one\nLine two  ", reference_answer="\t Answer. \n")
    assert created.text == "Line one\nLine two"
    assert created.reference_answer == "Answer."


def test_markup_characters_are_kept_exactly() -> None:
    assert QuestionCreate(text="<b>bold</b> & more", reference_answer="x").text == (
        "<b>bold</b> & more"
    )


@pytest.mark.parametrize(
    "kwargs", [{}, {"text": None, "reference_answer": None}], ids=["no-fields", "both-none"]
)
def test_update_requires_at_least_one_field(kwargs: dict[str, None]) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        QuestionUpdate(**kwargs)


def test_update_may_give_a_single_field() -> None:
    update = QuestionUpdate(text="x")
    assert update.text == "x"
    assert update.reference_answer is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "   "},
        {"reference_answer": ""},
        {"text": "я" * (QUESTION_TEXT_MAX_LENGTH + 1)},
        {"reference_answer": "я" * (REFERENCE_ANSWER_MAX_LENGTH + 1)},
    ],
    ids=["blank-text", "blank-answer", "long-text", "long-answer"],
)
def test_update_validates_a_given_field_like_create(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        QuestionUpdate(**kwargs)
