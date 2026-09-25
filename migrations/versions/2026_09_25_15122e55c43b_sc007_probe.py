"""sc007 probe

Revision ID: 15122e55c43b
Revises: bba0b3665864
Create Date: 2026-09-25 15:47:45.377470+00:00

THROWAWAY — revert on `main` as soon as its release has been observed. This is the probe of
specs/003-database-questions/quickstart.md#v7 (SC-007, FR-010, task T056): it creates a table and
then fails, but only on Render, so CI passes and the failure happens in production. The expected
outcome is that the whole upgrade rolls back (the table never appears in Neon and
`alembic_version` stays at bba0b3665864), the new instance never becomes healthy, and the previous
release keeps serving.

Everywhere else the table is dropped again within the same upgrade, so the revision is a net no-op
and the test suite's model-versus-schema drift check stays green.
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15122e55c43b"
down_revision: str | Sequence[str] | None = "bba0b3665864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create `sc007_probe`, then fail on Render so the creation must roll back."""
    op.create_table("sc007_probe", sa.Column("id", sa.Integer(), primary_key=True))
    if os.environ.get("RENDER"):
        raise RuntimeError("SC-007 probe")
    op.drop_table("sc007_probe")


def downgrade() -> None:
    """Nothing to undo: off Render the upgrade leaves no trace."""
