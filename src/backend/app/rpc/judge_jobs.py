"""判题作业的构建与结果落库（远程 gRPC 节点共用）。

- build_job_bundle：读取提交/题目/测试点（仅元数据），换算有效限制，
  原子认领（pending→judging），产出 JobBundle 作业描述（含 data_version 指纹）；
  测试点数据本体由节点经 FetchProblemData 拉取（stream_problem_data）。
- apply_job_result：把节点回传的判题结果写回 DB 与 MinIO（幂等，可重复应用）。

data_version 指纹 = sha256(测试点数量 | 最大 updated_at)，按**判定集**计算：
练习/比赛=生效集（active_case_ids），验题=暂存集（pending_case_ids，空则退化生效集）；
晋升必然改变生效集指纹，节点据此做 <problem_id>-<version> 本地缓存。
题目 / 测试点经 problems.api 读取；终态回写（通过率计数 / 验题状态机 / 榜单 / 满分基准）
经 ProblemService / ContestService 上下文端口，本模块不直查比赛模型（check_import_rules 规则 6）。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.enums import RuleType, SubmissionStatus, SubmitType
from app.models.judge import SandboxConfig, Submission
from app.repositories.judge import JudgeRepository
from app.services import problem as problems
from app.services.contest import ContestService
from app.services.problem import ProblemService

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
    """单个测试点的派发元数据（数据本体不进作业描述：节点经 FetchProblemData
    按 data_version 拉取并本地缓存，见 stream_problem_data / docs/contracts/judge.md）。"""
    test_case_id: str
    name: str


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
    # ACM 赛制短路：节点在首个非 accepted 测试点后停止执行（docs/contracts/judge.md 赛制计分）
    stop_on_failure: bool = False


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


@dataclass(frozen=True)
class RunCodeOutcome:
    """节点回传的用户自测结果：dispatch_run_code 的返回值（不落库）。"""
    request_id: str
    status: str
    output: bytes
    error_message: str | None
    time_used_ms: int
    memory_used_kb: int | None


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


async def compute_data_version(db, problem, *, verify: bool = False) -> tuple[str, list[problems.TestCase]]:
    """数据指纹 + 判定集排序行。

    练习 / 比赛 = 生效集；验题提交（verify=True）= 暂存集（NULL 退化生效集）。
    """
    rows = await problems.list_judged_cases(db, problem, verify=verify)
    latest = max((r.updated_at for r in rows), default=None)
    raw = f"{len(rows)}|{latest.isoformat() if latest else 'empty'}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32], rows


async def build_job_bundle(db, submission_id: uuid.UUID) -> JobBundle | None:
    """构建作业描述（测试点仅元数据）并原子认领（pending→judging）。

    返回 None 表示提交不存在 / 已被其他执行方认领 / 前置校验失败（校验失败会直接落 system_error）。
    """
    repository = JudgeRepository()
    submission = await db.get(Submission, submission_id)
    if submission is None:
        return None
    # 原子认领：仅当仍为 pending 时置 judging，杜绝双执行方并发判同一题；
    # 认领失败说明已被其他执行方处理，静默放弃。
    # updated_at 刷新为认领时刻：judging 滞留判定（5 分钟判死）以此为基准
    claimed = (
        await db.execute(
            update(Submission)
            .where(Submission.id == submission_id, Submission.status == SubmissionStatus.PENDING)
            .values(
                status=SubmissionStatus.JUDGING,
                error_message=None,
                updated_at=datetime.now(timezone.utc),
            )
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

    # 判定集：验题提交判暂存集（先试新点），练习 / 比赛恒用生效集
    is_verify = submission.submit_type == SubmitType.VERIFY
    data_version, cases = await compute_data_version(db, problem, verify=is_verify)
    if not cases:
        await _finish_with_error(db, repository, submission, "no test cases")
        return None
    missing = [c for c in cases if not c.input_oss_id or not c.expected_output_oss_id]
    if missing:
        await _finish_with_error(db, repository, submission, "test case storage reference is missing")
        return None

    limits, compile_limits = resolve_limits(problem, config)
    code = submission.code.encode("utf-8")
    # ACM 赛制短路标记：首个非 accepted 测试点后节点停止执行后续测试点
    stop_on_failure = (
        submission.submit_type == SubmitType.CONTEST
        and submission.contest_id is not None
        and submission.rule_type == RuleType.ACM
    )
    # 仅携带元数据；测试点数据本体由节点经 FetchProblemData 拉取（本地缓存按 data_version）
    case_files = tuple(
        TestCaseFile(test_case_id=str(case.id), name=case.name or str(case.sort_order))
        for case in cases
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
        cases=case_files,
        stop_on_failure=stop_on_failure,
    )


async def _finish_with_error(db, repository: JudgeRepository, submission: Submission, message: str) -> None:
    await repository.finish_submission(
        db, submission, status=SubmissionStatus.SYSTEM_ERROR, score=0, time_used_ms=0, memory_used_kb=None, error_message=message
    )
    # 终态回写（验题状态机推进 / 通过率计数豁免）经题目上下文端口
    await ProblemService(db).on_submission_finalized(submission, SubmissionStatus.SYSTEM_ERROR)
    await db.commit()


async def apply_job_result(db, outcome: JudgeOutcome, *, storage) -> bool:
    """节点回传结果落库；返回是否成功应用（提交不存在/非 judging 返回 False）。"""
    repository = JudgeRepository()
    sid = uuid.UUID(outcome.submission_id)
    submission = await db.get(Submission, sid)
    if submission is None or submission.status != SubmissionStatus.JUDGING:
        return False

    # 分数在服务端按赛制派生（docs/contracts/judge.md「赛制计分」）：
    # - ACM（二值）：全部测试点通过 = 单题满分，否则 0；测试点不设分值。
    #   短路执行（stop_on_failure）下节点仅回传已执行测试点，无部分分可泄露。
    # - IOI / 练习 / 验题（部分计分）：测试点分值一致，单点 = 满分 ÷ 测试点数，
    #   仅通过计分；比赛提交的单题满分基准经比赛上下文端口获取（不直查 ContestProblem）。
    # 节点可能回传少于全部测试点的结果（ACM 短路），未执行测试点不落结果行。
    contest_service = ContestService(db)
    problem_service = ProblemService(db)
    cases = outcome.cases
    case_count = len(cases)
    full = _FULL_SCORE
    if submission.submit_type == SubmitType.CONTEST and submission.contest_id is not None:
        full = (
            await contest_service.full_score_for(submission.contest_id, submission.problem_id)
            or _FULL_SCORE
        )
    acm = submission.rule_type == RuleType.ACM
    base, extra = divmod(full, case_count) if case_count else (0, 0)

    total_score = 0
    max_time = 0
    max_memory: int | None = None
    for index, case in enumerate(cases):
        test_case = await problems.get_test_case(db, uuid.UUID(case.test_case_id))
        if test_case is None:
            continue
        accepted = case.status == SubmissionStatus.ACCEPTED
        if acm:
            score = 0
        else:
            score = base + (1 if index < extra else 0) if accepted and case_count else 0
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
    if acm:
        total_score = full if outcome.status == SubmissionStatus.ACCEPTED else 0
    await repository.finish_submission(
        db, submission,
        status=outcome.status or SubmissionStatus.SYSTEM_ERROR,
        score=total_score,
        time_used_ms=max_time,
        memory_used_kb=max_memory,
        error_message=outcome.error_message,
    )
    # 终态回写（同事务内顺序执行，任一失败整体回滚）：
    # 1. 题目上下文：通过率计数 + 验题状态机推进（verify/system_error 豁免由端口内判断）
    await problem_service.on_submission_finalized(submission, outcome.status or SubmissionStatus.SYSTEM_ERROR)
    # 2. 比赛上下文：榜单条件更新（封榜期 / 补题 / system_error 不计）
    await contest_service.on_submission_finalized(submission, outcome.status or SubmissionStatus.SYSTEM_ERROR)
    await db.commit()
    # 3. commit 后失效榜单缓存：服务层失效发生在事务提交前，并发读可能在删除与提交
    #    之间回填旧榜单；结束后为永久缓存，必须补删保证最终一致
    if submission.submit_type == SubmitType.CONTEST and submission.contest_id is not None:
        await contest_service.invalidate_board_cache(submission.contest_id)
    return True


async def stream_problem_data(db, problem_id: uuid.UUID, requested_version: str | None = None):
    """按 (path, content) 产出题目数据文件；供网关流式下发。

    双集合语义：按请求的 data_version 匹配候选集（生效集 / 验题暂存集）；
    未携带或无匹配时回退生效集。
    """

    def _fingerprint(rows: list[problems.TestCase]) -> str:
        latest = max((r.updated_at for r in rows), default=None)
        raw = f"{len(rows)}|{latest.isoformat() if latest else 'empty'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    problem = await problems.get_problem(db, problem_id)
    if problem is None:
        return
    storage = get_storage()
    candidates = [
        (await problems.list_active_cases(db, problem)),
        await problems.list_judged_cases(db, problem, verify=True),
    ]
    chosen = candidates[0]
    if requested_version:
        for rows in candidates:
            if rows and _fingerprint(rows) == requested_version:
                chosen = rows
                break
    data_version, cases = _fingerprint(chosen), chosen
    manifest = json.dumps({"data_version": data_version, "case_count": len(cases)})
    yield _MANIFEST_OBJECT_NAME, manifest.encode()
    for case in cases:
        input_bytes, _ = await storage.get_bytes(case.input_oss_id)
        expected_bytes, _ = await storage.get_bytes(case.expected_output_oss_id)
        yield case_data_name(str(case.id), "in"), input_bytes
        yield case_data_name(str(case.id), "out"), expected_bytes
