"""Create runs table.

Revision ID: 003
Revises: 002
Create Date: 2026-04-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create run status types, the runs table, and its session index.

    Returns:
        None.
    """
    run_status = postgresql.ENUM(
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        name="run_status",
        create_type=False,
    )
    run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("query_snapshot", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(op.f("ix_runs_session_id"), "runs", ["session_id"], unique=False)


def downgrade() -> None:
    """Remove the runs table, its index, and the run-status type.

    Returns:
        None.
    """
    op.drop_index(op.f("ix_runs_session_id"), table_name="runs")
    op.drop_table("runs")
    postgresql.ENUM(name="run_status").drop(op.get_bind(), checkfirst=True)
