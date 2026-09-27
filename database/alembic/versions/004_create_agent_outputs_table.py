"""Create agent_outputs table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create persistent structured agent outputs and lookup indexes.

    Returns:
        None.
    """
    op.create_table(
        "agent_outputs",
        sa.Column("output_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("output_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("output_id"),
    )
    op.create_index(op.f("ix_agent_outputs_session_id"), "agent_outputs", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_outputs_run_id"), "agent_outputs", ["run_id"], unique=False)


def downgrade() -> None:
    """Remove agent-output indexes and the agent_outputs table.

    Returns:
        None.
    """
    op.drop_index(op.f("ix_agent_outputs_run_id"), table_name="agent_outputs")
    op.drop_index(op.f("ix_agent_outputs_session_id"), table_name="agent_outputs")
    op.drop_table("agent_outputs")
