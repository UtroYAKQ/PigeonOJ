"""problems 模块对外门面（唯一出口）。

judge 等模块只允许 `from app.modules.problems.api import ...`：
- ORM 模型再导出（跨模块查询 / 外键引用）
- 题目 / 测试点查询函数
- 验题状态机钩子（pending 查询、邀请校验、代码快照回写、结果回写）
- ProblemService（验题发起等管理操作）
"""
from app.modules.problems.models import (
    Problem,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    ProblemVerificationInvite,
    TestCase,
    UserCodeDraft,
)
from app.modules.problems.service import (
    ProblemService,
    attach_verification_code,
    can_manage_problem,
    complete_verification,
    get_pending_verification,
    get_problem,
    get_test_case,
    list_formal_cases,
    validate_verification_invite,
)

__all__ = [
    "Problem",
    "ProblemTag",
    "ProblemTagRelation",
    "ProblemVerification",
    "ProblemVerificationInvite",
    "TestCase",
    "UserCodeDraft",
    "ProblemService",
    "attach_verification_code",
    "can_manage_problem",
    "complete_verification",
    "get_pending_verification",
    "get_problem",
    "get_test_case",
    "list_formal_cases",
    "validate_verification_invite",
]
