"""沙箱节点架构：sandbox_configs 表 + 默认语言配置种子

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# docs/contracts/judge.md 语言限制换算：cpp17 为基准；python/java 按平台默认比例
_DEFAULT_CONFIGS = [
    # language, time_ratio, memory_ratio, memory_min_mb, output_limit_kb, cpu_cores, process_limit
    ("python3.12", 3.0, 2.0, 128, 1024, 1, 16),
    ("cpp17", 1.0, 1.0, 0, 1024, 1, 32),
    ("java21", 2.0, 2.0, 256, 1024, 1, 48),
]


def upgrade() -> None:
    now = sa.text("now()")
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sandbox_configs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("language", sa.String(32), nullable=False, unique=True),
        sa.Column("cpu_limit", sa.Integer()),
        sa.Column("time_ratio", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("memory_ratio", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("memory_min_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("process_limit", sa.Integer()),
        sa.Column("filesystem_readonly", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("output_limit_kb", sa.Integer()),
        sa.Column("disk_quota_mb", sa.Integer()),
        sa.Column("cpu_cores", sa.Integer()),
        sa.Column("network_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    for lang, tr, mr, mm, ol, cores, procs in _DEFAULT_CONFIGS:
        op.execute(
            sa.text(
                "INSERT INTO sandbox_configs (id, language, time_ratio, memory_ratio, memory_min_mb,"
                " output_limit_kb, cpu_cores, process_limit) VALUES (gen_random_uuid(), :lang, :tr, :mr, :mm, :ol, :cores, :procs)"
                " ON CONFLICT (language) DO NOTHING"
            ).bindparams(lang=lang, tr=tr, mr=mr, mm=mm, ol=ol, cores=cores, procs=procs)
        )


def downgrade() -> None:
    op.drop_table("sandbox_configs")
