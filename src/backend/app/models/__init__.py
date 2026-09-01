"""ORM 模型聚合包：import 本包即注册全部表到 Base.metadata。

alembic autogenerate 与测试建表都依赖本聚合；
每张业务表的归属文件见 docs/contracts/ 对应模块契约。
"""
from app.models.admin import Report  # noqa: F401
from app.models.audit import ExceptionLog, LoginLog, RequestLog  # noqa: F401
from app.models.contest import Contest, ContestProblem, ContestRanking, ContestRegistration  # noqa: F401
from app.models.judge import SandboxConfig, Submission, SubmissionTestCaseResult  # noqa: F401
from app.models.problem import (  # noqa: F401
    Problem,
    ProblemCounter,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    TestCase,
)
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.problem_set import ProblemSet, ProblemSetItem  # noqa: F401
from app.models.user import Role, User, UserRole, UserSession  # noqa: F401

__all__ = [
    "Report",
    "ExceptionLog",
    "LoginLog",
    "RequestLog",
    "SandboxConfig",
    "Submission",
    "SubmissionTestCaseResult",
    "Problem",
    "ProblemCounter",
    "ProblemTag",
    "ProblemTagRelation",
    "ProblemVerification",
    "TestCase",
    "ProblemSet",
    "ProblemSetItem",
    "Contest",
    "ContestProblem",
    "ContestRegistration",
    "ContestRanking",
    "SystemConfig",
    "Role",
    "User",
    "UserRole",
    "UserSession",
]
