"""initial schema: users / user_sessions / roles / user_roles / user_token_stats /
system_configs / model_configs / request_logs / login_logs / exception_logs / reports

表结构与 docs/contracts/users.md、admin.md、ai.md、community.md 对齐。
迁移 SQL 是表结构唯一来源（docs/contracts/index.md）。
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid(value: str) -> str:
    return str(uuid.UUID(value))


# 角色种子：docs/security.md（scope 语义由 user_roles 承载）
ROLE_SEEDS = [
    (_uuid("11111111-1111-1111-1111-111111111111"), "admin", "系统管理员",
     "全部能力：用户管理、系统配置、运维、公开比赛、团队、AI 出题等"),
    (_uuid("22222222-2222-2222-2222-222222222222"), "tutor", "导师",
     "创建团队、创建公开比赛、管理题目、使用 AI（含出题）"),
    (_uuid("33333333-3333-3333-3333-333333333333"), "user", "普通用户",
     "浏览题目 / 题单 / 比赛、提交、AI 聊天 / 改代码 / 编译纠错（默认角色）"),
    (_uuid("44444444-4444-4444-4444-444444444444"), "team_creator", "团队创建者",
     "团队内全部管理：邀请 / 成员 / 题库 / 题单 / 比赛 / AI 出题，含「分配管理员」"),
    (_uuid("55555555-5555-5555-5555-555555555555"), "team_admin", "团队管理员",
     "同 team_creator，但不含「分配管理员」"),
    (_uuid("66666666-6666-6666-6666-666666666666"), "team_member", "团队成员",
     "查看团队题单 / 比赛、提交、AI 聊天"),
]

# 系统配置种子（docs/contracts/admin.md system_configs 配置项举例）
CONFIG_SEEDS = [
    ("site", "site.name", "PigeonOJ", "站点名称"),
    ("site", "site.logo", "", "站点 Logo"),
    ("site", "site.icp", "", "ICP 备案号"),
    ("site", "site.default_theme", "light", "默认主题样式"),
    ("site", "site.register_enabled", True, "是否开放注册"),
    ("auth_email", "email.code.expire_seconds", 600, "邮箱验证码有效期（秒）"),
    ("auth_email", "email.code.resend_seconds", 60, "验证码重发间隔（秒）"),
    ("auth_email", "email.code.max_attempts", 5, "验证码最大尝试次数"),
    ("team", "invite.expire_hours", 72, "团队邀请链接默认有效期（小时）"),
    ("team", "team.apply.review_rule", "manual", "加入团队审批规则（manual / auto）"),
    ("contest", "contest.freeze_default_seconds", 3600, "封榜默认时长（秒）"),
    ("contest", "contest.penalty_factor_minutes", 20, "罚时系数（分钟）"),
    ("sandbox", "sandbox.judge_concurrency", 8, "全局判题并发上限"),
    ("sandbox", "sandbox.cooldown_seconds", 10, "提交冷却时长（秒）"),
    ("log", "log.retention_days", 30, "日志保留天数"),
    ("community", "community.feature_switches", {"solution": True, "post": True, "comment": True}, "社区功能开关"),
]


def upgrade() -> None:
    now = sa.text("now()")

    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(64), nullable=False),
        sa.Column("avatar_url", sa.String(512)),
        sa.Column("signature", sa.String(255)),
        sa.Column("theme", sa.String(32), nullable=False, server_default=sa.text("'light'")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_status", "users", ["status"])

    # ---- user_sessions ----
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("device_info", sa.String(255)),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("token", name="uq_user_sessions_token"),
    )
    op.create_index("ix_user_sessions_user_expires_revoked", "user_sessions", ["user_id", "expires_at", "revoked_at"])

    # ---- roles / user_roles ----
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("scope", sa.String(8), nullable=False, server_default=sa.text("'global'")),
        sa.Column("object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("user_id", "role_id", "scope", "object_id", name="uq_user_roles_user_role_scope_object"),
    )

    # ---- system_configs ----
    op.create_table(
        "system_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("config_key", sa.String(128), nullable=False),
        sa.Column("config_value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("category", "config_key", name="uq_system_configs_category_key"),
    )

    # ---- request_logs ----
    op.create_table(
        "request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("extra", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_request_logs_user_created", "request_logs", ["user_id", "created_at"])
    op.create_index("ix_request_logs_path_created", "request_logs", ["path", "created_at"])
    op.create_index("ix_request_logs_created", "request_logs", ["created_at"])

    # ---- login_logs ----
    op.create_table(
        "login_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("email", sa.String(255)),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_login_logs_user_created", "login_logs", ["user_id", "created_at"])
    op.create_index("ix_login_logs_created", "login_logs", ["created_at"])

    # ---- exception_logs ----
    op.create_table(
        "exception_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("traceback", sa.Text()),
        sa.Column("request_id", sa.String(64)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_exception_logs_created", "exception_logs", ["created_at"])
    op.create_index("ix_exception_logs_level_created", "exception_logs", ["level", "created_at"])

    # ---- reports ----
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_reports_status_created", "reports", ["status", "created_at"])

    # ---- 种子数据：角色 + 系统配置 ----
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("description", sa.Text()),
        ),
        [{"id": rid, "code": code, "name": name, "description": desc} for rid, code, name, desc in ROLE_SEEDS],
    )
    op.bulk_insert(
        sa.table(
            "system_configs",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("category", sa.String()),
            sa.column("config_key", sa.String()),
            sa.column("config_value", postgresql.JSONB()),
            sa.column("description", sa.Text()),
        ),
        [
            {"id": uuid.uuid4(), "category": cat, "config_key": key, "config_value": value, "description": desc}
            for cat, key, value, desc in CONFIG_SEEDS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_status_created", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_exception_logs_level_created", table_name="exception_logs")
    op.drop_index("ix_exception_logs_created", table_name="exception_logs")
    op.drop_table("exception_logs")
    op.drop_index("ix_login_logs_created", table_name="login_logs")
    op.drop_index("ix_login_logs_user_created", table_name="login_logs")
    op.drop_table("login_logs")
    op.drop_index("ix_request_logs_created", table_name="request_logs")
    op.drop_index("ix_request_logs_path_created", table_name="request_logs")
    op.drop_index("ix_request_logs_user_created", table_name="request_logs")
    op.drop_table("request_logs")
    op.drop_table("system_configs")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("ix_user_sessions_user_expires_revoked", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")
