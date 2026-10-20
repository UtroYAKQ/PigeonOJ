"""Persistent synchronized resolver sessions.

Revision ID: 0039
Revises: 0038
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scoreboard_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("playing", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("speed", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("anchor_at", sa.DateTime(timezone=True)),
        sa.Column("last_command_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision >= 0 AND cursor >= 0", name="ck_scoreboard_session_progress"),
        sa.CheckConstraint("speed IN (1,2,4)", name="ck_scoreboard_session_speed"),
    )


def downgrade() -> None:
    op.drop_table("scoreboard_sessions")
