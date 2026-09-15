"""组织化改造切换：团队题全部改引用制 + tutor 全局角色下线（破坏性，生产无重要数据）

- 团队直建题清理：删除 team_id 非空且 referenced_at 为空（直建产生）的团队题目及其从属数据
  （测试点 / 验题 / 计数 / 标签关系 / 题单条目 / 比赛编排 / 提交与判题结果随 FK 或显式清理）；
  保留引用产生的快照题（referenced_at 非空）
- tutor 下线：存量 tutor 全局授权删除（用户降为 user），移除 tutor 角色种子；
  全站题目 / 题单 / 比赛创建权收归 admin，出题收敛到组织题库

Revision ID: 0041
Revises: 0040
"""
from __future__ import annotations

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

TUTOR_ROLE_ID = "22222222-2222-2222-2222-222222222222"


def upgrade() -> None:
    # 1) 团队直建题及其从属数据（破坏性清理；无外键级联的从属表显式清理）
    op.execute(
        """
        DELETE FROM submission_test_case_results WHERE submission_id IN (
            SELECT s.id FROM submissions s
            JOIN problems p ON p.id = s.problem_id
            WHERE p.team_id IS NOT NULL AND p.referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM submissions WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM problem_verifications WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM test_cases WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM problem_counters WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM problem_tag_relations WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM problem_set_items WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        """
        DELETE FROM contest_problems WHERE problem_id IN (
            SELECT id FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL
        )
        """
    )
    op.execute(
        "DELETE FROM problems WHERE team_id IS NOT NULL AND referenced_at IS NULL"
    )

    # 2) tutor 下线：授权删除（用户降为 user 默认角色），移除角色种子
    op.execute(
        f"""
        DELETE FROM user_roles WHERE role_id = '{TUTOR_ROLE_ID}' AND scope = 'global'
        """
    )
    op.execute(
        f"""
        DELETE FROM roles WHERE id = '{TUTOR_ROLE_ID}' AND code = 'tutor'
        """
    )


def downgrade() -> None:
    # tutor 角色恢复（授权不可恢复）；团队直建题不恢复（破坏性清理不可逆）
    op.execute(
        """
        INSERT INTO roles (id, code, name, description, created_at)
        VALUES (
            '22222222-2222-2222-2222-222222222222', 'tutor', '导师',
            '创建团队、创建公开比赛、管理题目', now()
        )
        ON CONFLICT (id) DO NOTHING
        """
    )
