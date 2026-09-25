"""create questions and boot counter

Revision ID: 1b6f9e8f822d
Revises:
Create Date: 2026-09-25 13:26:19.003920+00:00

Creates the first product table, `questions`, and the single-row `boot_counter` that makes
persistence observable, with its one row `(1, 0)`. Written with plain SQLAlchemy types rather
than the application's, so it stays valid however the models change later.
See specs/003-database-questions/data-model.md#5-alembic_version--owned-by-alembic.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b6f9e8f822d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("reference_answer", sa.String(5000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_table(
        "boot_counter",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("boots", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_boot_counter")),
        sa.CheckConstraint("id = 1", name=op.f("ck_boot_counter_single_row")),
    )
    boot_counter = sa.table("boot_counter", sa.column("id"), sa.column("boots"))
    op.bulk_insert(boot_counter, [{"id": 1, "boots": 0}])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("boot_counter")
    op.drop_table("questions")
