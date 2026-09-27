"""Add generated_files JSONB to sessions.

Revision ID: 002
Revises: 001
Create Date: 2026-04-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add generated-file metadata storage to existing sessions.

    Returns:
        None.
    """
    op.add_column(
        "sessions",
        sa.Column(
            "generated_files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove generated-file metadata storage from sessions.

    Returns:
        None.
    """
    op.drop_column("sessions", "generated_files")
