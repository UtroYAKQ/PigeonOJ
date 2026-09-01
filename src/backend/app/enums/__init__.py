"""全局枚举常量包：消除魔法字符串，统一定义各模块状态值。

数据库列的 server_default 仍用字符串（ORM 限制）；枚举用于业务代码类型安全与自动补全。
所有枚举按业务域拆分到子模块，此文件统一导出以保持向后兼容。
"""
from __future__ import annotations

from app.enums.admin import ReportAction, ReportStatus, ReportTargetType
from app.enums.audit import LogLevel, LoginAction
from app.enums.contest import ContestStatus, ContestType, RegistrationStatus, RuleType
from app.enums.judge import SubmissionStatus, SubmitType
from app.enums.problem import (
    CaseStatus,
    ProblemScope,
    ProblemSetStatus,
    ProblemSetVisibility,
    ProblemStatus,
    ProblemVisibility,
    TagStatus,
    VerificationStatus,
)
from app.enums.system_config import ConfigCategory
from app.enums.user import Theme, UserRoleScope, UserStatus

__all__ = [
    # 用户域
    "UserStatus",
    "Theme",
    "UserRoleScope",
    # 题库域
    "ProblemStatus",
    "ProblemVisibility",
    "ProblemScope",
    "TagStatus",
    "VerificationStatus",
    "CaseStatus",
    "ProblemSetStatus",
    "ProblemSetVisibility",
    # 判题域
    "SubmitType",
    "SubmissionStatus",
    # 比赛域
    "ContestType",
    "RuleType",
    "ContestStatus",
    "RegistrationStatus",
    # 管理域
    "ReportStatus",
    "ReportAction",
    "ReportTargetType",
    # 审计域
    "LoginAction",
    "LogLevel",
    # 系统配置域
    "ConfigCategory",
]
