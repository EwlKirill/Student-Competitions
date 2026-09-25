"""Question schemas: the validation boundary for writes, and the shape of public reads.

Input is checked when a caller builds `QuestionCreate` or `QuestionUpdate`, so invalid input
raises `pydantic.ValidationError` before any service function runs and can never reach the
database (FR-014). Each field is stripped of surrounding whitespace first, then must be non-empty
and within its limit, counted in Unicode code points; everything inside — line breaks, Cyrillic,
`<`, `&` — is kept exactly (FR-017).

See specs/003-database-questions/data-model.md#3-schemas--appschemasquestionpy.
"""

from typing import Annotated, Self

from pydantic import StringConstraints, model_validator
from sqlmodel import SQLModel

QUESTION_TEXT_MAX_LENGTH = 1000
REFERENCE_ANSWER_MAX_LENGTH = 5000
"""Also the column lengths in `app.models.question`, so the schema and the column cannot drift."""

QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=QUESTION_TEXT_MAX_LENGTH)
]
ReferenceAnswer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=REFERENCE_ANSWER_MAX_LENGTH),
]


class QuestionCreate(SQLModel):
    text: QuestionText
    reference_answer: ReferenceAnswer


class QuestionUpdate(SQLModel):
    """A partial update: a field left out keeps its stored value, but at least one is given."""

    text: QuestionText | None = None
    reference_answer: ReferenceAnswer | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if self.text is None and self.reference_answer is None:
            raise ValueError("at least one of text or reference_answer must be given")
        return self


class QuestionPublic(SQLModel):
    """What a public page may show of a question.

    It has no `reference_answer` field, so a template handed this view cannot display one: the
    rule "answers never reach a public page" is structural rather than a template convention
    (FR-022).
    """

    id: int
    text: str
