"""路由层依赖装配点（组合根，docs/architecture.md 依赖注入约定）。

路由层一律通过本模块获取依赖（FastAPI Annotated 注入）：
- 认证身份与 `XxxServiceDep` 服务 Provider 均从 deps 导入；路由不直接 import
  `app.services`、`app.core.dependency`、`get_db` / `SessionLocal`；
- Provider 负责构造 service/repo 与跨上下文端口装配（组合根）；接口使用 Protocol，
  以便测试经 `dependency_overrides` 替换；
- 同一请求内多个 Provider 共享请求级 db 会话（FastAPI 依赖缓存，get_db 单例）；
- 事务提交归属 Service（get_db 出口统一 commit），路由不再显式 commit。
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
from app.services.admin import (
    AdminConfigService,
    LogService,
    ReportService,
    SandboxService,
    TeamAdminService,
)
from app.services.community import CommunityService
from app.services.contest import ContestService
from app.services.file import FileService
from app.services.judge import (
    GatewaySubmissionDispatcher,
    SelfTestService,
    SubmissionService,
)
from app.services.org import OrgService
from app.services.problem import ProblemService
from app.services.problem_import import ProblemImportService
from app.services.problem_set import ProblemSetService
from app.services.system_config import ConfigService, get_site_public_configs
from app.services.tag import TagService
from app.services.team import TeamService
from app.services.team_space import TeamSpaceService
from app.services.user import AuthService, UserService

SessionDep = Annotated[AsyncSession, Depends(get_db)]
"""请求级数据库会话（仅供 Provider 构造 / 系统基础端点使用，路由不提交事务）。"""


# ---- 基础设施 Provider ----


def get_config_service(db: SessionDep) -> ConfigService:
    return ConfigService(db)


ConfigServiceDep = Annotated[ConfigService, Depends(get_config_service)]


def get_dispatcher(db: SessionDep) -> GatewaySubmissionDispatcher:
    """交题收尾适配器：commit → dispatch（判题 rpc 在业务侧的唯一触点）。"""
    return GatewaySubmissionDispatcher(db)


SubmissionDispatcherDep = Annotated[GatewaySubmissionDispatcher, Depends(get_dispatcher)]


# ---- 各上下文服务 Provider ----


def get_user_service(db: SessionDep) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_auth_service(
    db: SessionDep,
    users: UserServiceDep,
    config: ConfigServiceDep,
) -> AuthService:
    """认证服务：用户公开视图（UserViewPort）与配置服务构造注入。"""
    return AuthService(db, config=config, user_view=users)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_tag_service(db: SessionDep) -> TagService:
    return TagService(db)


TagServiceDep = Annotated[TagService, Depends(get_tag_service)]


def get_problem_service(db: SessionDep) -> ProblemService:
    return ProblemService(db)


ProblemServiceDep = Annotated[ProblemService, Depends(get_problem_service)]


def get_problem_import_service(db: SessionDep) -> ProblemImportService:
    return ProblemImportService(db)


ProblemImportServiceDep = Annotated[ProblemImportService, Depends(get_problem_import_service)]


def get_submission_service(
    db: SessionDep,
    problems: ProblemServiceDep,
    dispatcher: SubmissionDispatcherDep,
) -> SubmissionService:
    """判题服务：验题端口（ProblemVerificationPort）与派发端口构造注入。"""
    return SubmissionService(db, verification=problems, dispatcher=dispatcher)


SubmissionServiceDep = Annotated[SubmissionService, Depends(get_submission_service)]


def get_self_test_service(db: SessionDep, config: ConfigServiceDep) -> SelfTestService:
    return SelfTestService(db, config=config)


SelfTestServiceDep = Annotated[SelfTestService, Depends(get_self_test_service)]


def get_file_service() -> FileService:
    """FileService 无状态（不持有 db 会话）。"""
    return FileService()


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def get_team_service(db: SessionDep, config: ConfigServiceDep) -> TeamService:
    return TeamService(db, config=config)


TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]


def get_problem_set_service(
    db: SessionDep,
    problems: ProblemServiceDep,
    teams: TeamServiceDep,
    submissions: SubmissionServiceDep,
    dispatcher: SubmissionDispatcherDep,
) -> ProblemSetService:
    """题单服务：题库详情 / 团队角色 / 提交创建与派发端口构造注入。"""
    return ProblemSetService(
        db,
        problem_detail=problems,
        team_roles=teams,
        submission_creator=submissions,
        dispatcher=dispatcher,
    )


ProblemSetServiceDep = Annotated[ProblemSetService, Depends(get_problem_set_service)]


def get_contest_service(
    db: SessionDep,
    config: ConfigServiceDep,
    submissions: SubmissionServiceDep,
    problems: ProblemServiceDep,
    teams: TeamServiceDep,
    dispatcher: SubmissionDispatcherDep,
) -> ContestService:
    """比赛服务：判题上下文端口（ContestSubmitter）、题库详情 / 团队角色 / 派发端口装配。"""
    return ContestService(
        db,
        submitter=submissions,
        dispatcher=dispatcher,
        problem_detail=problems,
        submission_detail=submissions,
        team_roles=teams,
        config=config,
    )


ContestServiceDep = Annotated[ContestService, Depends(get_contest_service)]


def get_org_service(db: SessionDep, problems: ProblemServiceDep) -> OrgService:
    """组织服务：组织题库视图经 ProblemDetailPort 装配（避免路由层跨 Service 串联）。"""
    return OrgService(db, problems=problems)


OrgServiceDep = Annotated[OrgService, Depends(get_org_service)]


def get_team_space_service(
    db: SessionDep,
    teams: TeamServiceDep,
    problems: ProblemServiceDep,
    problem_sets: ProblemSetServiceDep,
    contests: ContestServiceDep,
    submissions: SubmissionServiceDep,
    self_test: SelfTestServiceDep,
    dispatcher: SubmissionDispatcherDep,
) -> TeamSpaceService:
    """团队空间门面：团队上下文题目 / 题单 / 比赛的统一入口（含跨上下文端口装配）。"""
    return TeamSpaceService(
        db,
        teams,
        problems,
        contests,
        submissions,
        problem_sets,
        self_test=self_test,
        dispatcher=dispatcher,
    )


TeamSpaceServiceDep = Annotated[TeamSpaceService, Depends(get_team_space_service)]


def get_community_service(
    db: SessionDep,
    problems: ProblemServiceDep,
    config: ConfigServiceDep,
) -> CommunityService:
    """社区服务：题目可见性门控复用 ProblemService（community.md「数据所有权」）。"""
    return CommunityService(db, problems, config)


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
    """SandboxService 走 Redis 注册表 / 网关节点视图，不持有 db 会话。"""
    return SandboxService()


SandboxServiceDep = Annotated[SandboxService, Depends(get_sandbox_service)]


def get_team_admin_service(
    teams: TeamServiceDep,
    space: TeamSpaceServiceDep,
) -> TeamAdminService:
    """管理后台团队视图：团队基础信息 + 团队空间资源计数统一门面。"""
    return TeamAdminService(teams, space)


TeamAdminServiceDep = Annotated[TeamAdminService, Depends(get_team_admin_service)]


# ---- 系统基础 ----


async def get_site_configs(db: SessionDep) -> SitePublicConfig:
    return await get_site_public_configs(db)


SiteConfigsDep = Annotated[SitePublicConfig, Depends(get_site_configs)]