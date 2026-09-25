"""The `questions` table: a short knowledge prompt and the teacher's reference answer.

See specs/003-database-questions/data-model.md#1-question--table-questions. Input is validated
by the schemas in `app.schemas.question` before it reaches this model; the column lengths below
are a backstop that PostgreSQL enforces and SQLite does not.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.question import QUESTION_TEXT_MAX_LENGTH, REFERENCE_ANSWER_MAX_LENGTH


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: int | None = Field(default=None, primary_key=True)
    text: str = Field(sa_column=Column(String(QUESTION_TEXT_MAX_LENGTH), nullable=False))
    reference_answer: str = Field(
        sa_column=Column(String(REFERENCE_ANSWER_MAX_LENGTH), nullable=False)
    )
    """The correct answer used for scoring. Never rendered on a public page (FR-022)."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by every update."""
