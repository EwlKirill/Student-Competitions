"""seed sample questions

Revision ID: bba0b3665864
Revises: 1b6f9e8f822d
Create Date: 2026-09-25 13:29:11.908682+00:00

Inserts the sample questions the home page shows, exactly once per database: Alembic records the
revision as applied, so no restart, redeploy or repeated `upgrade head` can insert them again
(FR-019, FR-020). See specs/003-database-questions/research.md#d6.

A frozen snapshot: the table is described here with `sa.table` rather than imported from
`app.models`, and nothing is imported from `app`, so this file stays valid however the model
changes later. Once applied anywhere shared, the content below must not be edited; change it
through a new migration instead. The tests read `SAMPLE_QUESTIONS` from this module, so there is
one source of truth for "the sample questions".
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bba0b3665864"
down_revision: str | Sequence[str] | None = "1b6f9e8f822d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SAMPLE_QUESTIONS: list[dict[str, str]] = [
    {
        "text": "What is the boiling point of water at sea level, in degrees Celsius?",
        "reference_answer": "100 °C (212 °F) at standard atmospheric pressure.",
    },
    {
        "text": "Name the largest planet in the Solar System.",
        "reference_answer": "Jupiter.",
    },
    {
        "text": 'Who wrote the novel "Nineteen Eighty-Four"?',
        "reference_answer": (
            "George Orwell (the pen name of Eric Arthur Blair); it was published in 1949."
        ),
    },
    {
        "text": "Explain in one or two sentences why the daytime sky appears blue.",
        "reference_answer": (
            "Sunlight is scattered by air molecules (Rayleigh scattering), and shorter blue "
            "wavelengths are scattered far more strongly than longer red ones, so blue light "
            "reaches the eye from every direction of the sky."
        ),
    },
    {
        "text": "What is the chemical formula of water, and what does it describe?",
        "reference_answer": (
            "H₂O: each molecule consists of two hydrogen atoms bonded to one oxygen atom."
        ),
    },
    {
        "text": (
            "Яка найдовша річка, що протікає територією України?\n"
            "Назвіть її та приблизну довжину в межах країни."
        ),
        "reference_answer": (
            "Дніпро — близько 981 км у межах України (загальна довжина — 2 201 км)."
        ),
    },
]
"""In display order. One is Ukrainian and spans two lines, so production visibly proves
non-Latin text and line breaks end to end."""

questions = sa.table(
    "questions",
    sa.column("text", sa.String),
    sa.column("reference_answer", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Upgrade schema."""
    # One timestamp for all rows, so their public order (created_at, then id) is the order above.
    now = datetime.now(UTC)
    op.bulk_insert(
        questions,
        [{**sample, "created_at": now, "updated_at": now} for sample in SAMPLE_QUESTIONS],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        questions.delete().where(
            questions.c.text.in_([sample["text"] for sample in SAMPLE_QUESTIONS])
        )
    )
