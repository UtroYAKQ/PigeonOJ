"""判题域枚举。"""
from __future__ import annotations

from enum import StrEnum


class SubmitType(StrEnum):
    PRACTICE = "practice"
    CONTEST = "contest"
    VERIFY = "verify"


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    JUDGING = "judging"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILE_ERROR = "compile_error"
    SYSTEM_ERROR = "system_error"
