"""判题作业的构建与结果落库（远程 gRPC 节点共用）。

- build_job_bundle：读取提交/题目/测试点，换算有效限制，从 MinIO 取数据本体，
  原子认领（pending→judging），产出 JobBundle 作业描述（含 data_version 指纹）。
- apply_job_result：把节点回传的判题结果写回 DB 与 MinIO（幂等，可重复应用）。

data_version 指纹 = sha256(测试点数量 | 最大 updated_at)；替换测试点必然改变指纹，
节点据此做 <problem_id>-<version> 本地缓存。
题目 / 测试点经 problems.api 读取；验题结果回写走 complete_verification 钩子。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select, update

from app.enums import SubmissionStatus, SubmitType
from app.models.judge import SandboxConfig, Submission
from app.repositories.judge import JudgeRepository
from app.services import problem as problems

from app.core.storage import get_storage

# 练习 / 验题单题满分（docs/contracts/judge.md：得分由服务端按通过比例派生）
_FULL_SCORE = 100
# FetchProblemData 数据包内的固定文件名（判题节点 datacache 按同名约定解析）
_MANIFEST_OBJECT_NAME = "manifest.json"


def case_data_name(test_case_id: str, kind: str) -> str:
    """数据包内测试点文件名：cases/<id>.in | .out（节点缓存目录相对路径）。"""
    return f"cases/{test_case_id}.{kind}"


@dataclass(frozen=True)
class ResourceLimits:
    """有效资源限制（已按语言比例换算；与节点侧 executor 同语义）。"""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    output_limit_kb: int = 1024
    process_limit: int = 32
    cpu_cores: int = 1


@dataclass(frozen=True)
class TestCaseFile:
    """单个测试点的派发文件（数据本体已从 MinIO 读出）。"""
    test_case_id: str
    name: str
    input: bytes
    expected_output: bytes


@dataclass(frozen=True)
class JobBundle:
    """作业描述：build_job_bundle 的产物，send_job 逐字段序列化为 judge_pb2.SubmitJob 下发。"""
    submission_id: str
    language: str
    code: bytes
    limits: ResourceLimits
    compile_limits: ResourceLimits
    problem_id: str
    data_version: str
    cases: tuple[TestCaseFile, ...]


@dataclass(frozen=True)
class CaseOutcome:
    """单个测试点的回传结果（judge_pb2.CaseResult 的进程内表示）。"""
    test_case_id: str
    status: str
    time_used_ms: int
    memory_used_kb: int | None
    output: bytes


@dataclass(frozen=True)
class JudgeOutcome:
    """节点回传的判题结果整体：apply_job_result 的入参（落库前进程内表示）。"""
    submission_id: str
    status: str
    time_used_ms: int
    memory_used_kb: int | None
    error_message: str | None
    cases: tuple[CaseOutcome, ...]


def resolve_limits(problem, config: SandboxConfig | None) -> tuple[ResourceLimits, ResourceLimits]:
    """按 sandbox_configs 语言比例换算有效限制（docs/contracts/judge.md 语言限制换算）。"""
    time_ratio = config.time_ratio if config else 1.0
    memory_ratio = config.memory_ratio if config else 1.0
    memory_min = config.memory_min_mb if config else 0
    output_kb = (config.output_limit_kb if config else None) or 1024
    cores = (config.cpu_cores if config else None) or 1
    procs = (config.process_limit if config else None) or 32
    eff_time = max(1, int(problem.time_limit_ms * time_ratio))
    eff_mem = max(int(problem.memory_limit_mb * memory_ratio), memory_min)
    limits = ResourceLimits(
        time_limit_ms=eff_time,
        memory_limit_mb=eff_mem,
        output_limit_kb=output_kb,
        cpu_cores=cores,
        process_limit=procs,
    )
    compile_limits = ResourceLimits(
        time_limit_ms=max(10_000, eff_time * 10),
        memory_limit_mb=eff_mem,
        output_limit_kb=output_kb,
        cpu_cores=cores,
        process_limit=procs,
    )
    return limits, compile_limits


async def compute_data_version(db, problem_id: uuid.UUID) -> tuple[str, list[problems.TestCase]]:
    """数据指纹 + 排序后的正式测试点列表。"""
    rows = await problems.list_formal_cases(db, problem_id)
    latest = max((r.updated_at for r in rows), default=None)
    raw = f"{len(rows)}|{latest.isoformat() if latest else 'empty'}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32], rows


async def build_job_bundle(db, submission_id: uuid.UUID, *, storage) -> JobBundle | None:
    """构建作业描述并原子认领（pending→judging）。

    返回 None 表示提交不存在 / 已被其他执行方认领 / 前置校验失败（校验失败会直接落 system_error）。
    """
    repository = JudgeRepository()
    submission = await db.get(Submission, submission_id)
    if submission is None:
        return None
    # 原子认领：仅当仍为 pending 时置 judging，杜绝双执行方并发判同一题；
    # 认领失败说明已被其他执行方处理，静默放弃
    claimed = (
        await db.execute(
            update(Submission)
            .where(Submission.id == submission_id, Submission.status == SubmissionStatus.PENDING)
            .values(status=SubmissionStatus.JUDGING, error_message=None)
        )
    ).rowcount
    if not claimed:
        return None
    problem = await problems.get_problem(db, submission.problem_id)
    if problem is None:
        await db.rollback()
        return None
    config = await db.scalar(select(SandboxConfig).where(SandboxConfig.language == submission.language))
    if config is not None and not config.is_enabled:
        await _finish_with_error(db, repository, submission, "language is disabled")
        return None

    data_version, cases = await compute_data_version(db, submission.problem_id)
    if not cases:
        await _finish_with_error(db, repository, submission, "no test cases")
        return None
    missing = [c for c in cases if not c.input_oss_id or not c.expected_output_oss_id]
    if missing:
        await _finish_with_error(db, repository, submission, "test case storage reference is missing")
        return None

    limits, compile_limits = resolve_limits(problem, config)
    code = submission.code.encode("utf-8")
    case_files: list[TestCaseFile] = []
    for case in cases:
        input_bytes, _ = await storage.get_bytes(case.input_oss_id)
        expected_bytes, _ = await storage.get_bytes(case.expected_output_oss_id)
        case_files.append(
            TestCaseFile(
                test_case_id=str(case.id),
                name=case.name or str(case.sort_order),
                input=input_bytes,
                expected_output=expected_bytes,
            )
        )

    await db.commit()
    return JobBundle(
        submission_id=str(submission_id),
        language=submission.language,
        code=code,
        limits=limits,
        compile_limits=compile_limits,
        problem_id=str(submission.problem_id),
        data_version=data_version,
        cases=tuple(case_files),
    )


async def _finish_with_error(db, repository: JudgeRepository, submission: Submission, message: str) -> None:
    await repository.finish_submission(
        db, submission, status=SubmissionStatus.SYSTEM_ERROR, score=0, time_used_ms=0, memory_used_kb=None, error_message=message
    )
    await _complete_verification_if_needed(db, submission)
    await db.commit()


async def _complete_verification_if_needed(db, submission: Submission) -> None:
    """验题提交完成后回调题库模块状态机（passed → problems.is_verified 等回写）。"""
    if submission.submit_type != SubmitType.VERIFY or not submission.verification_id:
        return
    await problems.complete_verification(
        db,
        submission.verification_id,
        passed=submission.status == SubmissionStatus.ACCEPTED,
        verifier_id=submission.user_id,
    )


async def apply_job_result(db, outcome: JudgeOutcome, *, storage) -> bool:
    """节点回传结果落库；返回是否成功应用（提交不存在/非 judging 返回 False）。"""
    repository = JudgeRepository()
    sid = uuid.UUID(outcome.submission_id)
    submission = await db.get(Submission, sid)
    if submission is None or submission.status != SubmissionStatus.JUDGING:
        return False

    # 分数在服务端派生：测试点分值一致（docs/architecture.md），单题得分 = 通过比例折算 0-100
    cases = outcome.cases
    case_count = len(cases)
    base, extra = divmod(_FULL_SCORE, case_count) if case_count else (0, 0)

    total_score = 0
    max_time = 0
    max_memory: int | None = None
    for index, case in enumerate(cases):
        test_case = await problems.get_test_case(db, uuid.UUID(case.test_case_id))
        if test_case is None:
            continue
        accepted = case.status == SubmissionStatus.ACCEPTED
        score = base + (1 if index < extra else 0) if accepted and case_count else 0
        if accepted:
            total_score += score
        max_time = max(max_time, case.time_used_ms)
        if case.memory_used_kb:
            max_memory = max(max_memory or 0, case.memory_used_kb)
        output_key = f"submissions/{sid}/cases/{test_case.id}/output"
        await storage.put_bytes(output_key, case.output or b"", "text/plain")
        await repository.write_case_result(
            db, sid, test_case,
            status=case.status, time_used_ms=case.time_used_ms,
            memory_used_kb=case.memory_used_kb, score=score,
            output=output_key,
        )
    await repository.finish_submission(
        db, submission,
        status=outcome.status or SubmissionStatus.SYSTEM_ERROR,
        score=total_score,
        time_used_ms=max_time,
        memory_used_kb=max_memory,
        error_message=outcome.error_message,
    )
    # 验题提交：回写 problem_verifications 与 problems.is_verified
    await _complete_verification_if_needed(db, submission)
    await db.commit()
    return True


async def stream_problem_data(db, problem_id: uuid.UUID):
    """按 (path, content) 产出题目数据文件；供网关流式下发。"""
    storage = get_storage()
    data_version, cases = await compute_data_version(db, problem_id)
    manifest = json.dumps({"data_version": data_version, "case_count": len(cases)})
    yield _MANIFEST_OBJECT_NAME, manifest.encode()
    for case in cases:
        input_bytes, _ = await storage.get_bytes(case.input_oss_id)
        expected_bytes, _ = await storage.get_bytes(case.expected_output_oss_id)
        yield case_data_name(str(case.id), "in"), input_bytes
        yield case_data_name(str(case.id), "out"), expected_bytes
