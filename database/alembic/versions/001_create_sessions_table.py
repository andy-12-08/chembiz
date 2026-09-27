"""Create sessions table.

Revision ID: 001
Revises:
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial sessions table and JSONB file-metadata storage.

    Returns:
        None.
    """
    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )


def downgrade() -> None:
    """Remove the sessions table created by this migration.

    Returns:
        None.
    """
    op.drop_table("sessions")
