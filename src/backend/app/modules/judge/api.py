"""judge 模块对外门面（唯一出口）。

其他模块只允许 `from app.modules.judge.api import ...`：
contests 模块（榜单 / 比赛提交）接入时经此处创建提交与查询判题状态。
"""
from app.modules.judge.dispatcher import active_judge_count
from app.modules.judge.gateway import dispatch_submission
from app.modules.judge.service import SubmissionService

__all__ = [
    "SubmissionService",
    "active_judge_count",
    "dispatch_submission",
]
