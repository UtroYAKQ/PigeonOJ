"""跨上下文端口（消费方拥有接口，docs/architecture.md 依赖注入约定）。

端口只声明协作者契约，实现由 `app/api/deps.py` 装配；服务之间禁止在方法体内
互相构造（check_import_rules.py 规则 8 守护）。使用 `Protocol` 而非具体类，
使消费方不依赖提供方实现，也便于测试以替身替换组合图。
"""
from __future__ import annotations

import uuid
from typing import Protocol


class SubmissionDispatcher(Protocol):
    """提交收尾端口：先提交事务持久化，再派发判题作业（顺序不可调换）。"""

    async def dispatch(self, submission: object) -> None: ...


class SubmissionCreator(Protocol):
    """判题提交创建端口（仅创建待派发提交，不提交事务）。"""

    async def create(
        self, user: object, body: object, *, bypass_visibility: bool = False
    ) -> object: ...


class SubmissionDetailPort(Protocol):
    """提交详情装配端口（访问控制由调用方完成）。"""

    async def build_detail(self, submission: object) -> object: ...


class ProblemDetailPort(Protocol):
    """题库只读装配端口（详情 / 组织视图 / 列表计数器与标签回填）。"""

    async def get_detail(
        self, problem_id: uuid.UUID, viewer: object | None, *, bypass_visibility: bool = False
    ) -> object: ...

    async def get_org_problem_detail(
        self, org_id: uuid.UUID, problem_id: uuid.UUID, user: object | None
    ) -> object: ...

    async def list_org_problems(
        self,
        org_id: uuid.UUID,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[object], int]: ...

    async def verification_flags(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, bool]: ...

    async def attach_counters(self, summaries: list) -> None: ...

    async def attach_tags(self, summaries: list) -> None: ...

    async def attach_solve_status(self, summaries: list, viewer: object | None) -> None: ...


class ProblemVerificationPort(Protocol):
    """验题邀请端口（发起验题时复用题库上下文状态机）。"""

    async def init_verification(
        self, user: object, problem_id: uuid.UUID, invite_expires_hours: int | None
    ) -> object: ...


class TeamRolePort(Protocol):
    """团队角色判定端口（其他上下文判断团队可见性 / 管理权）。"""

    async def has_team_roles(
        self, user: object | None, team_id: uuid.UUID, *, level: str = "member"
    ) -> bool: ...


class UserViewPort(Protocol):
    """用户公开视图装配端口（认证上下文组装登录返回）。"""

    async def to_public(self, user: object) -> object: ...


class SelfTestPort(Protocol):
    """自测运行端口（团队空间门控通过后复用判题自测链路）。"""

    async def create_order(
        self,
        user: object,
        problem_id: uuid.UUID,
        body: object,
        *,
        bypass_visibility: bool = False,
    ) -> object: ...

    async def run_once(self, order: object, user_id: uuid.UUID) -> object: ...