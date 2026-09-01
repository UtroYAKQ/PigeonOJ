"""比赛域枚举。"""
from __future__ import annotations

from enum import StrEnum


class ContestType(StrEnum):
    """比赛归属（docs/contracts/contests.md）：团队比赛随 teams 模块开放。"""

    PUBLIC = "public"
    TEAM = "team"


class RuleType(StrEnum):
    """赛制计分规则。"""

    ACM = "ACM"
    IOI = "IOI"


class ContestStatus(StrEnum):
    """比赛生命周期（按时间推进，contest_transition 任务维护）。"""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    FINISHED = "finished"


class RegistrationStatus(StrEnum):
    """报名状态。"""

    REGISTERED = "registered"
    CANCELLED = "cancelled"
