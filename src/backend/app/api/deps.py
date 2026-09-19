"""路由层依赖装配点（组合点，docs/architecture.md 依赖注入约定）。

路由层一律通过本模块获取依赖（FastAPI Annotated 注入），
禁止直接 import app.services 构造服务（check_import_rules.py 规则 5 强制检查）。

约定（社区通用结构）：
- deps.py 是路由层唯一的依赖导入点：认证身份、db 会话、各上下文服务 Provider 均从此导入；
- Provider 内完成服务组装（含跨上下文端口装配），服务间依赖走构造注入而非函数内局部导入；
- 同一请求内多个 Provider 共享同一个请求级 db 会话（FastAPI 依赖缓存，get_db 单例）；
- 路由函数需要显式 commit 时另注入 SessionDep（与 Provider 内会话为同一实例）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
# 认证身份依赖：定义在 core.dependency（services 也复用），路由层统一经本模块导入
from app.core.dependency import (  # noqa: F401 —— re-export 供路由层导入
    get_bearer_token,
    get_current_admin,
    get_current_user,
    get_optional_user,
)
from app.schemas.admin import SitePublicConfig
from app.services.admin import AdminConfigService, LogService, ReportService, SandboxService
from app.services.community import CommunityService
from app.services.contest import ContestService
from app.services.file import FileService
from app.services.judge import SelfTestService, SubmissionService
from app.services.problem import ProblemService
from app.services.problem_import import ProblemImportService
from app.services.problem_set import ProblemSetService
from app.services.system_config import ConfigService, get_site_public_configs
from app.services.org import OrgService
from app.services.tag import TagService
from app.services.team import TeamService
from app.services.team_space import TeamSpaceService
from app.services.user import AuthService, UserService

SessionDep = Annotated[AsyncSession, Depends(get_db)]
"""请求级数据库会话（路由需要显式 commit 时使用）。"""


# ---- 各上下文服务 Provider ----


def get_auth_service(db: SessionDep) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_user_service(db: SessionDep) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_config_service(db: SessionDep) -> ConfigService:
    return ConfigService(db)


ConfigServiceDep = Annotated[ConfigService, Depends(get_config_service)]


def get_tag_service(db: SessionDep) -> TagService:
    return TagService(db)


TagServiceDep = Annotated[TagService, Depends(get_tag_service)]


def get_problem_service(db: SessionDep) -> ProblemService:
    return ProblemService(db)


ProblemServiceDep = Annotated[ProblemService, Depends(get_problem_service)]


def get_problem_import_service(db: SessionDep) -> ProblemImportService:
    return ProblemImportService(db)


ProblemImportServiceDep = Annotated[ProblemImportService, Depends(get_problem_import_service)]


def get_submission_service(db: SessionDep) -> SubmissionService:
    return SubmissionService(db)


SubmissionServiceDep = Annotated[SubmissionService, Depends(get_submission_service)]


def get_self_test_service(db: SessionDep) -> SelfTestService:
    return SelfTestService(db)


SelfTestServiceDep = Annotated[SelfTestService, Depends(get_self_test_service)]


def get_file_service() -> FileService:
    """FileService 无状态（不持有 db 会话）。"""
    return FileService()


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def get_problem_set_service(db: SessionDep) -> ProblemSetService:
    return ProblemSetService(db)


ProblemSetServiceDep = Annotated[ProblemSetService, Depends(get_problem_set_service)]


def get_contest_service(
    db: SessionDep,
    submission_service: SubmissionServiceDep,
) -> ContestService:
    """比赛服务：装配判题上下文端口（ContestSubmitter），替代路由层回调注入。"""
    return ContestService(db, submitter=submission_service)


ContestServiceDep = Annotated[ContestService, Depends(get_contest_service)]


def get_team_service(db: SessionDep) -> TeamService:
    return TeamService(db)


TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]


def get_org_service(db: SessionDep) -> OrgService:
    return OrgService(db)


OrgServiceDep = Annotated[OrgService, Depends(get_org_service)]


def get_team_space_service(
    db: SessionDep,
    teams: TeamServiceDep,
    problems: ProblemServiceDep,
    contests: ContestServiceDep,
    submissions: SubmissionServiceDep,
) -> TeamSpaceService:
    """团队空间门面：团队上下文题目 / 题单 / 比赛的统一入口（含跨上下文端口装配）。"""
    return TeamSpaceService(db, teams, problems, contests, submissions)


TeamSpaceServiceDep = Annotated[TeamSpaceService, Depends(get_team_space_service)]


def get_community_service(
    db: SessionDep,
    problems: ProblemServiceDep,
) -> CommunityService:
    """社区服务：题目可见性门控复用 ProblemService（community.md「数据所有权」）。"""
    return CommunityService(db, problems, ConfigService(db))


CommunityServiceDep = Annotated[CommunityService, Depends(get_community_service)]


# ---- admin 组合层服务（用例门面，非独立上下文）----


def get_admin_config_service(db: SessionDep) -> AdminConfigService:
    return AdminConfigService(db)


AdminConfigServiceDep = Annotated[AdminConfigService, Depends(get_admin_config_service)]


def get_log_service(db: SessionDep) -> LogService:
    return LogService(db)


LogServiceDep = Annotated[LogService, Depends(get_log_service)]


def get_report_service(db: SessionDep) -> ReportService:
    return ReportService(db)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


def get_sandbox_service() -> SandboxService:
    """SandboxService 走 Redis 注册表，不持有 db 会话。"""
    return SandboxService()


SandboxServiceDep = Annotated[SandboxService, Depends(get_sandbox_service)]


# ---- 系统基础 ----


async def get_site_configs(db: SessionDep) -> SitePublicConfig:
    return await get_site_public_configs(db)


SiteConfigsDep = Annotated[SitePublicConfig, Depends(get_site_configs)]
