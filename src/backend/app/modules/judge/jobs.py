"""判题作业的构建与结果落库（远程 gRPC 节点共用）。

- build_job_bundle：读取提交/题目/测试点，换算有效限制，从 MinIO 取数据本体，
  原子认领（pending→judging），产出可序列化的作业描述（含 data_version 指纹）。
- apply_job_result：把节点回传的判题结果写回 DB 与 MinIO（幂等，可重复应用）。

data_version 指纹 = sha256(测试点数量 | 最大 updated_at)；替换测试点必然改变指纹，
节点据此做 <problem_id>-<version> 本地缓存。
题目 / 测试点经 problems.api 读取；验题结果回写走 complete_verification 钩子。
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update

from app.modules.judge.models import SandboxConfig, Submission
from app.modules.judge.repository import JudgeRepository
from app.modules.problems import api as problems

from app.shared.infra.storage import get_storage


@dataclass(frozen=True)
class ResourceLimits:
    """有效资源限制（已按语言比例换算；与节点侧 executor 同语义）。"""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    output_limit_kb: int = 1024
    process_limit: int = 32
    cpu_cores: int = 1


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


async def build_job_bundle(db, submission_id: uuid.UUID, *, storage) -> dict[str, Any] | None:
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
            .where(Submission.id == submission_id, Submission.status == "pending")
            .values(status="judging", error_message=None)
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
    case_files: list[dict[str, Any]] = []
    for case in cases:
        input_bytes, _ = await storage.get_bytes(case.input_oss_id)
        expected_bytes, _ = await storage.get_bytes(case.expected_output_oss_id)
        case_files.append(
            {
                "test_case_id": str(case.id),
                "name": case.name or str(case.sort_order),
                "input": input_bytes,
                "expected_output": expected_bytes,
            }
        )

    await db.commit()
    return {
        "submission_id": str(submission_id),
        "language": submission.language,
        "code": code,
        "limits": limits,
        "compile_limits": compile_limits,
        "problem_id": str(submission.problem_id),
        "data_version": data_version,
        "cases": case_files,
    }


async def _finish_with_error(db, repository: JudgeRepository, submission: Submission, message: str) -> None:
    await repository.finish_submission(
        db, submission, status="system_error", score=0, time_used_ms=0, memory_used_kb=None, error_message=message
    )
    await _complete_verification_if_needed(db, submission)
    await db.commit()


async def _complete_verification_if_needed(db, submission: Submission) -> None:
    """验题提交完成后回调题库模块状态机（passed → problems.is_verified 等回写）。"""
    if submission.submit_type != "verify" or not submission.verification_id:
        return
    await problems.complete_verification(
        db,
        submission.verification_id,
        passed=submission.status == "accepted",
        verifier_id=submission.user_id,
    )


async def apply_job_result(db, payload: dict[str, Any], *, storage) -> bool:
    """节点回传结果落库；返回是否成功应用（提交不存在/非 judging 返回 False）。"""
    repository = JudgeRepository()
    submission_id = uuid.UUID(payload["submission_id"])
    submission = await db.get(Submission, submission_id)
    if submission is None or submission.status != "judging":
        return False

    # 分数在服务端派生：测试点分值一致（docs/architecture.md），单题得分 = 通过比例折算 0-100
    cases = payload.get("cases", [])
    case_count = len(cases)
    base, extra = divmod(100, case_count) if case_count else (0, 0)

    total_score = 0
    max_time = 0
    max_memory: int | None = None
    for index, case in enumerate(cases):
        test_case = await problems.get_test_case(db, uuid.UUID(case["test_case_id"]))
        if test_case is None:
            continue
        accepted = case["status"] == "accepted"
        score = base + (1 if index < extra else 0) if accepted and case_count else 0
        if accepted:
            total_score += score
        max_time = max(max_time, case.get("time_used_ms") or 0)
        if case.get("memory_used_kb"):
            max_memory = max(max_memory or 0, case["memory_used_kb"])
        output_key = f"submissions/{submission_id}/cases/{test_case.id}/output"
        await storage.put_bytes(output_key, case.get("output") or b"", "text/plain")
        await repository.write_case_result(
            db, submission_id, test_case,
            status=case["status"], time_used_ms=case.get("time_used_ms"),
            memory_used_kb=case.get("memory_used_kb"), score=score,
            output=output_key,
        )
    await repository.finish_submission(
        db, submission,
        status=payload.get("status", "system_error"),
        score=total_score,
        time_used_ms=max_time,
        memory_used_kb=max_memory,
        error_message=payload.get("error_message"),
    )
    # 验题提交：回写 problem_verifications 与 problems.is_verified
    await _complete_verification_if_needed(db, submission)
    await db.commit()
    return True


async def stream_problem_data(db, problem_id: uuid.UUID):
    """按 (path, content) 产出题目数据文件；供网关流式下发。"""
    storage = get_storage()
    data_version, cases = await compute_data_version(db, problem_id)
    yield "manifest.json", f'{{"data_version":"{data_version}","case_count":{len(cases)}}}'.encode()
    for case in cases:
        input_bytes, _ = await storage.get_bytes(case.input_oss_id)
        expected_bytes, _ = await storage.get_bytes(case.expected_output_oss_id)
        yield f"cases/{case.id}.in", input_bytes
        yield f"cases/{case.id}.out", expected_bytes
