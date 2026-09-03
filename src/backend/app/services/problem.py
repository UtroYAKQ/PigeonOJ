"""题库域服务：题目生命周期、标签、验题、测试点管理。"""
from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    CaseStatus,
    ProblemStatus,
    ProblemVisibility,
    SubmissionStatus,
    SubmitType,
    TagStatus,
    VerificationStatus,
)
from app.core.exceptions import (
    APIError,
    AUTH_FORBIDDEN,
    PARAM_FORMAT_INVALID,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    SYSTEM_UPSTREAM_FAILURE,
)
from app.core.redis import (
    get_redis,
    redis_delete,
    redis_get,
    redis_get_json,
    redis_set,
    redis_set_json,
)
from app.core.storage import get_storage
from app.core.dependency import is_admin, is_manager
from app.models.problem import (
    Problem,
    ProblemCounter,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    TestCase,
)
from app.models.judge import Submission
from app.repositories.problem import ProblemRepository, TagRepository, VerificationRepository
from app.repositories.judge import TestCaseRepository
from app.schemas.problem import (
    ProblemCreate,
    ProblemDetail,
    ProblemQuery,
    ProblemUpdate,
    SampleOut,
    SamplesUpdate,
    TestCaseListOut,
    TestCaseOut,
    TestCasesPatch,
    TestCasesUpdate,
    VerificationInitOut,
    VerificationInviteLink,
    VerificationInviteOut,
)

logger = logging.getLogger(__name__)

VERIFY_INVITE_KEY_PREFIX = "verify_invite:"
VERIFY_INVITE_PROBLEM_PREFIX = "verify_invite_problem:"


def _uuid_list(raw: list | None) -> list[uuid.UUID]:
    """JSONB id 引用列表 → UUID 列表（NULL / 空数组 → 空列表）。"""
    return [uuid.UUID(str(v)) for v in raw] if raw else []


def derive_case_status(problem: Problem) -> str:
    """case_status 缓存值：由两集合与已验标记推导
    。"""
    if problem.pending_case_ids is None:
        return CaseStatus.OK if problem.active_case_ids else CaseStatus.EMPTY
    if getattr(problem, "pending_verified", False):
        return CaseStatus.VERIFIED
    return CaseStatus.TO_VERIFY if not problem.active_case_ids else CaseStatus.TO_REVERIFY


def staged_target(problem: Problem) -> tuple[list[uuid.UUID], bool]:
    """编辑视图目标状态：暂存集优先，否则生效集。返回 (ids, staged)。"""
    if problem.pending_case_ids is not None:
        return _uuid_list(problem.pending_case_ids), True
    return _uuid_list(problem.active_case_ids), False


def judged_case_ids(problem: Problem, *, verify: bool) -> list[uuid.UUID]:
    """判定集：验题提交按暂存集判（先试新点，NULL 退化生效集）；
    练习 / 比赛恒用生效集——未验证的暂存改动绝不影响正常判题。"""
    if verify and problem.pending_case_ids is not None:
        return _uuid_list(problem.pending_case_ids)
    return _uuid_list(problem.active_case_ids)


async def list_active_cases(db: AsyncSession, problem: Problem) -> list[TestCase]:
    """生效集行（判题唯一数据来源），按集合顺序。"""
    return await TestCaseRepository(db).list_by_ids(problem.id, _uuid_list(problem.active_case_ids))


async def list_judged_cases(db: AsyncSession, problem: Problem, *, verify: bool = False) -> list[TestCase]:
    """判定集行（verify=True 时为暂存集退化生效集，否则生效集）。"""
    return await TestCaseRepository(db).list_by_ids(problem.id, judged_case_ids(problem, verify=verify))


def needs_reverification(problem: Problem) -> bool:
    """重验精确判定：存在暂存改动，或样例晚于最近验题通过时间。"""
    if problem.verified_at is None:
        return True
    if problem.pending_case_ids is not None:
        return True
    return bool(
        problem.samples_updated_at and problem.samples_updated_at > problem.verified_at
    )


async def bump_counters(db: AsyncSession, problem_id: uuid.UUID, *, accepted: bool) -> None:
    """判题终态回写通过率计数（problem_counters upsert 原子累加，docs/contracts/judge.md）。

    统计口径由调用方保证：verify 提交与 system_error 不进入本函数。
    SQL 细节见 ProblemRepository.bump_counters。
    """
    await ProblemRepository(db).bump_counters(problem_id, accepted=accepted)


@dataclass(frozen=True)
class ProblemDetailData:
    """题目详情装配结果：get_detail → 路由 _detail 的进程内传输结构。"""

    problem: Problem
    samples: list[SampleOut]
    tags: list[str]
    can_manage: bool
    needs_reverification: bool
    # 通过率计数（problem_counters，无记录按 0）
    submission_count: int = 0
    accepted_count: int = 0


# 持有清理任务引用，防止 fire-and-forget 任务被 GC 中途回收
_cleanup_tasks: set[asyncio.Task] = set()


def schedule_object_cleanup(stale_keys: list[str]) -> None:
    """事务提交后异步清理 MinIO 旧对象（fire-and-forget，docs/contracts/problems.md）。"""
    if not stale_keys:
        return

    async def _cleanup(keys: list[str]) -> None:
        storage = get_storage()
        for key in keys:
            try:
                await storage.delete(key)
            except Exception:
                logger.exception("MinIO object cleanup failed: key=%s", key)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_cleanup(stale_keys))
    _cleanup_tasks.add(task)
    task.add_done_callback(_cleanup_tasks.discard)


class ProblemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.problems = ProblemRepository(db)
        self.tags = TagRepository(db)
        self.verifications = VerificationRepository(db)
        self.test_cases = TestCaseRepository(db)

    async def list_published(
        self, query: ProblemQuery, viewer: object | None = None,
    ) -> tuple[list[Problem], int]:
        viewer_id = getattr(viewer, "id", None)
        # scope=mine 全量视图仅 admin；其余管理角色（tutor 等）只看本人创建
        see_all = viewer is not None and await is_admin(self.db, viewer)
        return await self.problems.list_published(query, viewer_id, see_all)

    async def verification_flags(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, bool]:
        """返回 {problem_id: needs_reverification} 用于 scope=mine 列表。

        精确判定：存在暂存改动（pending 非NULL）或样例晚于最近验题通过时间。
        """
        if not problem_ids:
            return {}
        rows = await self.problems.verification_snapshot_fields(problem_ids)
        flags: dict[uuid.UUID, bool] = {}
        for row in rows:
            snapshot = SimpleNamespace(
                verified_at=row.verified_at,
                samples_updated_at=row.samples_updated_at,
                pending_case_ids=row.pending_case_ids,
            )
            flags[row.id] = needs_reverification(snapshot)
        return flags

    async def attach_counters(self, summaries: list) -> None:
        """按 id 批量回填通过率计数到 ProblemSummary（无计数行保持 0；API 层调用）。"""
        ids = {item.id for item in summaries}
        if not ids:
            return
        counters = await self.problems.counters_for(list(ids))
        for item in summaries:
            counter = counters.get(item.id)
            if counter is not None:
                item.submission_count = counter.submission_count
                item.accepted_count = counter.accepted_count

    async def attach_solve_status(self, summaries: list, viewer: object | None) -> None:
        """按 viewer 批量回填题库列表作答状态（未提交过的题保持 None=未提交过；API 层调用）。"""
        viewer_id = getattr(viewer, "id", None)
        if viewer_id is None or not summaries:
            return
        status_map = await self.problems.solve_status_map(
            viewer_id, [item.id for item in summaries]
        )
        for item in summaries:
            if item.id in status_map:
                item.solved = status_map[item.id]

    async def create(self, user: object, body: ProblemCreate) -> Problem:
        if not await is_manager(self.db, user):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)
        problem = Problem(
            title=body.title,
            background=body.background,
            description=body.description,
            input_description=body.input_description,
            output_description=body.output_description,
            note=body.note,
            solution=body.solution,
            visibility=body.visibility,
            time_limit_ms=body.time_limit_ms,
            memory_limit_mb=body.memory_limit_mb,
            difficulty=body.difficulty,
            owner_id=user.id,
        )
        problem = await self.problems.create(problem)
        if body.tags:
            await self._sync_tags(problem.id, body.tags)
        return problem

    async def get_detail(self, problem_id: uuid.UUID, user: object | None) -> ProblemDetailData:
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        can_manage = user is not None and await _can_manage(self.db, user, problem)
        if not can_manage and problem.status != ProblemStatus.PUBLISHED:
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        tags = await self.verifications.tag_names(problem_id)
        tag_names = sorted(tags)
        samples = self._samples_view(problem)
        counter = await self.db.get(ProblemCounter, problem_id)
        return ProblemDetailData(
            problem=problem,
            samples=samples,
            tags=tag_names,
            can_manage=can_manage,
            needs_reverification=(
                needs_reverification(problem) if problem.verified_at and problem.is_verified else False
            ),
            submission_count=counter.submission_count if counter else 0,
            accepted_count=counter.accepted_count if counter else 0,
        )

    async def get_cases_managed(self, user: object, problem_id: uuid.UUID) -> TestCaseListOut:
        """测试点列表（独立管理端点）：仅题目管理者（admin 或创建者）可读。

        详情响应一律不携带测试点（docs/contracts/problems.md 数据所有权），
        编辑器经本端点回读目标状态（暂存优先）。
        """
        problem = await self._require_manage(user, problem_id)
        cases = await self.list_cases_view(problem)
        ids, _staged = staged_target(problem)
        updated_at = await self.test_cases.max_updated_at(problem_id, ids)
        return TestCaseListOut(cases=cases, updated_at=updated_at)

    async def get_detail_view(self, problem_id: uuid.UUID, user: object | None) -> ProblemDetail:
        """路由侧装配：详情聚合 + 契约模型转换一步到位。

        路由层经 app/api/deps.py 注入本服务后无需再引用模块级装配函数。
        """
        return to_problem_detail(await self.get_detail(problem_id, user))

    async def on_submission_finalized(self, submission: Submission, status: str) -> None:
        """判题终态回写端口：通过率计数 + 验题状态机推进（judge 上下文唯一入口）。

        - 验题提交：无论终态如何都推进验题状态机（system_error 视为未通过）
        - 练习/比赛提交：回写通过率计数；verify（非真实作答）与 system_error（平台故障）不计入
          （docs/contracts/judge.md 统计口径）
        """
        if submission.submit_type == SubmitType.VERIFY:
            if submission.verification_id:
                await complete_verification(
                    self.db,
                    submission.verification_id,
                    passed=status == SubmissionStatus.ACCEPTED,
                    verifier_id=submission.user_id,
                )
            return
        if status == SubmissionStatus.SYSTEM_ERROR:
            return
        await bump_counters(
            self.db, submission.problem_id, accepted=status == SubmissionStatus.ACCEPTED
        )

    @staticmethod
    def _samples_view(problem: Problem) -> list[SampleOut]:
        """problems.samples JSONB → 展示结构（name 按序派生，不暴露内部 id）。"""
        return [
            SampleOut(
                name=f"sample{index}",
                input=item.get("input") or "",
                output=item.get("output") or "",
                explanation=item.get("explanation") or "",
            )
            for index, item in enumerate(problem.samples or [], start=1)
            if isinstance(item, dict)
        ]

    async def update(self, user: object, problem_id: uuid.UUID, body: ProblemUpdate) -> Problem:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑", 409)
        if body.title is not None:
            problem.title = body.title
        if body.background is not None:
            problem.background = body.background
        if body.description is not None:
            problem.description = body.description
        if body.input_description is not None:
            problem.input_description = body.input_description
        if body.output_description is not None:
            problem.output_description = body.output_description
        if body.note is not None:
            problem.note = body.note or None
        if body.solution is not None:
            problem.solution = body.solution
        if body.visibility is not None:
            problem.visibility = body.visibility
        if body.time_limit_ms is not None:
            problem.time_limit_ms = body.time_limit_ms
        if body.memory_limit_mb is not None:
            problem.memory_limit_mb = body.memory_limit_mb
        if body.difficulty is not None:
            problem.difficulty = body.difficulty
        if body.tags is not None:
            await self._sync_tags(problem.id, body.tags)
        problem.updated_at = datetime.now()
        await self.db.flush()
        return problem

    async def replace_cases(self, user: object, problem_id: uuid.UUID, body: TestCasesUpdate) -> None:
        """全量替换**暂存集**（PUT 语义；生效集不动，验题通过后晋升）。"""
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)
        try:
            storage = get_storage()
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc
        created: list[TestCase] = []
        uploaded_keys: list[str] = []
        try:
            for idx, item in enumerate(body.cases):
                if not item.input and not item.expected_output:
                    raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                input_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/input"
                output_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/output"
                await storage.put_bytes(input_key, (item.input or "").encode("utf-8"), "text/plain; charset=utf-8")
                uploaded_keys.append(input_key)
                await storage.put_bytes(output_key, (item.expected_output or "").encode("utf-8"), "text/plain; charset=utf-8")
                uploaded_keys.append(output_key)
                created.append(TestCase(
                    problem_id=problem_id,
                    name=item.name or str(idx + 1),
                    input_oss_id=input_key,
                    expected_output_oss_id=output_key,
                    sort_order=item.sort_order or idx + 1,
                ))
        except Exception as exc:
            for key in uploaded_keys:
                try:
                    await storage.delete(key)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc
        # 行不可变：旧行退役留档（历史判题结果外键恒有效），目标状态整体写入暂存集
        await self.problems.add_test_cases(created)
        problem.pending_case_ids = [str(row.id) for row in created]
        problem.pending_verified = False  # 任何新的暂存写入都会使「已验」标记失效
        problem.case_status = derive_case_status(problem)
        problem.cases_revision += 1
        await self.db.flush()

    async def list_cases_view(self, problem: Problem) -> list[TestCaseOut]:
        """管理角色编辑用：目标状态（暂存优先）回读内容，附 staged 标记。"""
        ids, staged = staged_target(problem)
        rows = await self.test_cases.list_by_ids(problem.id, ids)
        return await self._cases_out(problem.id, rows, staged=staged)

    async def _cases_out(
        self, problem_id: uuid.UUID, rows: list[TestCase], *, staged: bool,
    ) -> list[TestCaseOut]:
        storage = get_storage()
        out: list[TestCaseOut] = []
        for tc in rows:
            input_text = None
            expected_text = None
            if tc.input_oss_id:
                raw, _ = await storage.get_bytes(tc.input_oss_id)
                input_text = raw.decode("utf-8", errors="replace")
            if tc.expected_output_oss_id:
                raw, _ = await storage.get_bytes(tc.expected_output_oss_id)
                expected_text = raw.decode("utf-8", errors="replace")
            out.append(TestCaseOut(
                id=str(tc.id),
                name=tc.name,
                sort_order=tc.sort_order,
                input=input_text,
                expected_output=expected_text,
                staged=staged,
            ))
        return out

    async def patch_cases(self, user: object, problem_id: uuid.UUID, body: TestCasesPatch) -> None:
        """增量更新**暂存集**（PATCH /problems/{id}/test-cases）：只改动提交的行。

        行不可变版本化：对既有点的任何有效变更生成新行（origin_id 指回原行），
        未改动点在目标状态中沿用原 id；delete_ids 表示目标状态中不含该点。
        生效集在晋升前不受影响。

        - upserts 带 id：改名 / 调序 / 换内容。input / expected_output 缺省或 null = 保持
          不变；传字符串则整体替换该侧内容，空字符串 = 显式清空（写入空对象），
          
        - upserts 不带 id：新增（输入输出不能全空；两侧同时显式置空同样拒绝）
        - 至少保留一个测试点：目标状态不允许为空（生效集非空后永不为空的不变式）
        """
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)
        if not body.upserts and not body.delete_ids:
            return  # 空 PATCH：不触碰任何集合状态

        base_ids, _staged = staged_target(problem)
        base_set = set(base_ids)
        rows_by_id = {tc.id: tc for tc in await self.test_cases.list_by_problem(problem_id)}
        upsert_ids = [item.id for item in body.upserts if item.id is not None]
        if len(upsert_ids) != len(set(upsert_ids)):
            raise APIError(PARAM_FORMAT_INVALID, "同一测试点被重复更新", 400)
        overlap = set(upsert_ids) & set(body.delete_ids)
        if overlap:
            raise APIError(PARAM_FORMAT_INVALID, "测试点不能同时更新和删除", 400)
        unknown = [cid for cid in upsert_ids + list(body.delete_ids) if cid not in base_set]
        if unknown:
            raise APIError(RESOURCE_NOT_FOUND, "测试点不存在", 404)
        try:
            storage = get_storage()
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc

        uploaded_keys: list[str] = []

        async def _upload(kind: str, content: str) -> str:
            key = f"problems/{problem_id}/cases/{uuid.uuid4()}/{'input' if kind == 'input' else 'output'}"
            await storage.put_bytes(key, content.encode("utf-8"), "text/plain; charset=utf-8")
            uploaded_keys.append(key)
            return key

        async def _resolve_side(row: TestCase, field: str, content: str | None) -> str:
            """None=沿用原引用；与存储内容一致则复用（避免无谓新版本）；否则上传新对象。"""
            oss_field = "input_oss_id" if field == "input" else "expected_output_oss_id"
            current_key = getattr(row, oss_field)
            if content is None:
                return current_key
            raw, _ = await storage.get_bytes(current_key)
            if raw.decode("utf-8", errors="replace") == content:
                return current_key
            return await _upload(field, content)

        # 目标序列：(位置键, id)。未触碰成员保持其在目标视图中的相对位置；
        # 被 upsert 触碰的成员 / 新增行使用提交的 sort_order（前端按全列表下标下发，允许空洞）
        entries: list[tuple[int, uuid.UUID]] = []
        sort_overrides: dict[uuid.UUID, int] = {
            item.id: item.sort_order for item in body.upserts if item.id is not None and item.sort_order
        }
        deleted = set(body.delete_ids)

        try:
            id_map: dict[uuid.UUID, uuid.UUID] = {}
            brand_new: list[tuple[int, uuid.UUID]] = []
            for index, item in enumerate(body.upserts):
                if item.id is None:
                    new_input = item.input or ""
                    new_output = item.expected_output or ""
                    if not new_input.strip() and not new_output.strip():
                        raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                    row = TestCase(
                        problem_id=problem_id,
                        name=item.name or str(index + 1),
                        input_oss_id=await _upload("input", new_input),
                        expected_output_oss_id=await _upload("output", new_output),
                        origin_id=None,
                        sort_order=item.sort_order or index + 1,
                    )
                    self.db.add(row)
                    await self.db.flush()
                    brand_new.append((item.sort_order or index + 1, row.id))
                    continue
                row = rows_by_id[item.id]
                provided = {
                    field: getattr(item, field)
                    for field in ("input", "expected_output")
                    if getattr(item, field) is not None
                }
                if len(provided) == 2 and all(not value.strip() for value in provided.values()):
                    raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能同时为空", 400)
                new_input_key = await _resolve_side(row, "input", item.input)
                new_output_key = await _resolve_side(row, "expected_output", item.expected_output)
                new_name = item.name if item.name is not None else row.name
                changed = (
                    new_input_key != row.input_oss_id
                    or new_output_key != row.expected_output_oss_id
                    or new_name != row.name
                )
                if changed:
                    # 行不可变：生成新版本行，origin_id 指回原行；原行退役留档（外键恒有效）
                    new_row = TestCase(
                        problem_id=problem_id,
                        origin_id=row.id,
                        name=new_name,
                        input_oss_id=new_input_key,
                        expected_output_oss_id=new_output_key,
                        sort_order=row.sort_order,
                    )
                    self.db.add(new_row)
                    await self.db.flush()
                    id_map[item.id] = new_row.id

            position_of = {cid: idx + 1 for idx, cid in enumerate(base_ids)}
            for cid in base_ids:
                if cid in deleted:
                    continue
                key = sort_overrides.get(cid) or position_of[cid]
                entries.append((key, id_map.get(cid, cid)))
            entries.extend(brand_new)
            entries.sort(key=lambda pair: pair[0])
            target = [cid for _, cid in entries]
            if not target:
                # 目标状态为空 = 删除全部测试点：违反「生效集非空后永不为空」不变式
                raise APIError(PARAM_FORMAT_INVALID, "至少保留一个测试点", 400)
            problem.pending_case_ids = [str(cid) for cid in target]
            problem.pending_verified = False  # 任何新的暂存写入都会使「已验」标记失效
            problem.case_status = derive_case_status(problem)
            problem.cases_revision += 1
            await self.db.flush()
        except Exception as exc:
            for key in uploaded_keys:
                try:
                    await storage.delete(key)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc

    async def apply_pending_cases(self, user: object, problem_id: uuid.UUID) -> Problem:
        """显式生效（点「保存」才晋升）：把已通过验题的暂存集晋升为生效集。

        前置：存在暂存改动且已打「已验待生效」标记；任何新的暂存写入都会清除标记。
        """
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可应用测试点", 409)
        if problem.pending_case_ids is None:
            raise APIError(RESOURCE_STATE_CONFLICT, "没有待生效的测试点改动", 409)
        if not problem.pending_verified:
            raise APIError(RESOURCE_STATE_CONFLICT, "测试点尚未通过验题，不能生效", 409)
        problem.active_case_ids = problem.pending_case_ids
        problem.pending_case_ids = None
        problem.pending_verified = False
        problem.case_status = derive_case_status(problem)
        problem.cases_revision += 1
        await self.db.flush()
        return problem

    async def replace_samples(self, user: object, problem_id: uuid.UUID, body: SamplesUpdate) -> None:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑样例", 409)
        # explanation 仅在非空时落键（JSONB 存量格式保持 {"input", "output"} 干净）
        problem.samples = [
            {
                "input": s.input,
                "output": s.output,
                **({"explanation": s.explanation} if s.explanation else {}),
            }
            for s in body.samples
        ]
        problem.samples_updated_at = datetime.now()
        problem.updated_at = datetime.now()
        await self.db.flush()

    async def publish(self, user: object, problem_id: uuid.UUID) -> Problem:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "已归档题目不可发布", 409)
        if not problem.is_verified:
            raise APIError(RESOURCE_STATE_CONFLICT, "题目未验题，不可发布", 409)
        if not problem.active_case_ids:
            raise APIError(RESOURCE_STATE_CONFLICT, "题目无正式测试点，不可发布", 409)
        if problem.pending_case_ids is not None:
            raise APIError(RESOURCE_STATE_CONFLICT, "测试点存在待验证的改动，请重新验题", 409)
        if problem.verified_at and problem.samples_updated_at and problem.samples_updated_at > problem.verified_at:
            raise APIError(RESOURCE_STATE_CONFLICT, "样例在验题通过后被修改，请重新验题", 409)
        problem.status = ProblemStatus.PUBLISHED
        problem.published_at = datetime.now()
        problem.updated_at = datetime.now()
        await self.db.flush()
        return problem

    async def archive(self, user: object, problem_id: uuid.UUID) -> Problem:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "题目已归档", 409)
        problem.status = ProblemStatus.ARCHIVED
        problem.updated_at = datetime.now()
        await self.db.flush()
        return problem

    async def _load_invite(self, problem_id: uuid.UUID) -> VerificationInviteLink | None:
        """返回题目当前有效的验题邀请链接（基于 Redis 反向索引）；无或已失效返回 None。"""
        token = await redis_get(f"{VERIFY_INVITE_PROBLEM_PREFIX}{problem_id}")
        if not token:
            return None
        payload = await redis_get_json(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
        if not isinstance(payload, dict) or "problem_id" not in payload:
            return None
        remaining = await get_redis().ttl(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
        if not isinstance(remaining, int) or remaining <= 0:
            return None
        return VerificationInviteLink(token=token, expires_at=datetime.now() + timedelta(seconds=remaining))

    async def get_verification_invite(self, user: object, problem_id: uuid.UUID) -> VerificationInviteLink | None:
        """查询题目当前有效的验题邀请链接（含权限校验）；无或已失效返回 None。"""
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await _can_manage(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        return await self._load_invite(problem_id)

    async def init_verification(self, user: object, problem_id: uuid.UUID, invite_expires_hours: int | None) -> VerificationInitOut:
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await _can_manage(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        pending = await self.verifications.get_pending(problem_id)

        # 自行验题：复用进行中的验题记录（若有），否则新建空白记录
        if invite_expires_hours is None:
            if pending is None:
                pending = await self.verifications.create(ProblemVerification(problem_id=problem_id))
            return VerificationInitOut(verification_id=str(pending.id), invite=None)

        # 生成邀请链接：若已有有效链接，直接复用，避免重复创建
        existing = await self._load_invite(problem_id)
        if existing is not None:
            if pending is None:
                pending = await self.verifications.create(ProblemVerification(problem_id=problem_id))
            return VerificationInitOut(verification_id=str(pending.id), invite=existing)

        token = secrets.token_urlsafe(32)[:64]
        ttl_seconds = int(invite_expires_hours * 3600)
        await redis_set_json(
            f"{VERIFY_INVITE_KEY_PREFIX}{token}",
            {"problem_id": str(problem_id)},
            ttl_seconds=ttl_seconds,
        )
        await redis_set(
            f"{VERIFY_INVITE_PROBLEM_PREFIX}{problem_id}",
            token,
            ttl_seconds=ttl_seconds,
        )
        if pending is None:
            pending = await self.verifications.create(ProblemVerification(problem_id=problem_id))
        invite = VerificationInviteLink(token=token, expires_at=datetime.now() + timedelta(seconds=ttl_seconds))
        return VerificationInitOut(verification_id=str(pending.id), invite=invite)

    async def resolve_invite(self, token: str) -> VerificationInviteOut:
        """解析验题邀请链接（数据源 Redis；返回题面与样例，不含正式测试点内容与题解）。"""
        payload = await redis_get_json(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
        if not isinstance(payload, dict) or "problem_id" not in payload:
            raise APIError(RESOURCE_NOT_FOUND, "邀请链接无效", 404)
        try:
            problem_id = uuid.UUID(str(payload["problem_id"]))
        except ValueError as exc:
            raise APIError(RESOURCE_NOT_FOUND, "邀请链接无效", 404) from exc
        remaining = await get_redis().ttl(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
        if remaining is not None and remaining < 0:
            raise APIError(RESOURCE_STATE_CONFLICT, "邀请链接已失效", 409)
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        return VerificationInviteOut(
            problem_id=str(problem.id),
            problem_title=problem.title,
            expires_at=datetime.now() + timedelta(seconds=remaining)
            if isinstance(remaining, int) and remaining > 0
            else None,
            background=problem.background,
            description=problem.description,
            input_description=problem.input_description,
            output_description=problem.output_description,
            note=problem.note,
            tags=await self.verifications.tag_names(problem.id),
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            samples=self._samples_view(problem),
        )

    async def _sync_tags(self, problem_id: uuid.UUID, tag_names: list[str]) -> None:
        await self.tags.delete_relations(problem_id)
        for name in tag_names:
            tag = await self.tags.get_by_name(name)
            if tag is None or tag.status != TagStatus.ACTIVE:
                raise APIError(PARAM_FORMAT_INVALID, f"标签不存在或已归档：{name}", 400)
            await self.tags.add_relation(problem_id, tag.id)

    async def _require_manage(self, user: object, problem_id: uuid.UUID) -> Problem:
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await _can_manage(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        return problem


async def _can_manage(db: AsyncSession, user: object, problem: Problem) -> bool:
    """题目管理权限（单一所有权模型，docs/security.md）：admin 管理全站题目；
    其余管理角色（tutor / team_creator）仅可管理本人创建的题目。"""
    if await is_admin(db, user):
        return True
    return problem.owner_id == user.id


def to_problem_detail(detail: ProblemDetailData) -> ProblemDetail:
    """题目详情装配：ProblemDetailData → 响应契约（测试点 / 题解仅管理角色可见）。

    题库路由（GET /problems/{id}）与题单路由（GET /problem-sets/{id}/problems/{pid}）共用，
    保证两个入口的详情结构与可见性门控完全一致（docs/contracts/problem-sets.md 统一入口）。
    """
    problem = detail.problem
    return ProblemDetail(
        id=problem.id,
        title=problem.title,
        background=problem.background,
        description=problem.description,
        input_description=problem.input_description,
        output_description=problem.output_description,
        note=problem.note,
        solution=problem.solution if detail.can_manage else None,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        status=problem.status,
        visibility=problem.visibility,
        is_verified=problem.is_verified,
        verified_by=problem.verified_by,
        verified_at=problem.verified_at,
        owner_id=problem.owner_id,
        published_at=problem.published_at,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
        difficulty=problem.difficulty,
        submission_count=detail.submission_count,
        accepted_count=detail.accepted_count,
        samples=detail.samples,
        tags=detail.tags,
        can_manage=detail.can_manage,
        needs_reverification=bool(detail.needs_reverification),
        case_status=problem.case_status,
        samples_updated_at=problem.samples_updated_at,
    )


async def get_problem(db: AsyncSession, problem_id: uuid.UUID) -> Problem:
    problem = await ProblemRepository(db).get_by_id(problem_id)
    if problem is None:
        raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
    return problem


async def get_test_case(db: AsyncSession, test_case_id: uuid.UUID) -> TestCase:
    tc = await TestCaseRepository(db).get_by_id(test_case_id)
    if tc is None:
        raise APIError(RESOURCE_NOT_FOUND, "测试点不存在", 404)
    return tc


async def can_manage_problem(db: AsyncSession, user: object, problem: Problem) -> bool:
    return await _can_manage(db, user, problem)


async def get_pending_verification(db: AsyncSession, problem_id: uuid.UUID) -> ProblemVerification | None:
    return await VerificationRepository(db).get_pending(problem_id)


async def validate_verification_invite(db: AsyncSession, verification_id: uuid.UUID, token: str | None) -> ProblemVerification:
    repo = VerificationRepository(db)
    verification = await repo.get_by_id(verification_id)
    if verification is None:
        raise APIError(RESOURCE_NOT_FOUND, "验题记录不存在", 404)
    return verification


async def attach_verification_code(
    db: AsyncSession,
    verification_id: uuid.UUID,
    user_id: uuid.UUID,
    code: str,
    language: str,
) -> Submission:
    repo = VerificationRepository(db)
    verification = await repo.get_by_id(verification_id)
    if verification is None:
        raise APIError(RESOURCE_NOT_FOUND, "验题记录不存在", 404)
    verification.code = code
    verification.language = language
    verification.verifier_id = user_id
    submission = Submission(
        user_id=user_id,
        problem_id=verification.problem_id,
        verification_id=verification_id,
        language=language,
        code=code,
        submit_type=SubmitType.VERIFY,
        status=SubmissionStatus.PENDING,
    )
    db.add(submission)
    await db.flush()
    return submission


async def complete_verification(
    db: AsyncSession,
    verification_id: uuid.UUID,
    *,
    passed: bool,
    verifier_id: uuid.UUID,
) -> None:
    repo = VerificationRepository(db)
    verification = await repo.get_by_id(verification_id)
    if verification is None:
        raise APIError(RESOURCE_NOT_FOUND, "验题记录不存在", 404)
    verification.status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
    verification.verifier_id = verifier_id
    verification.updated_at = datetime.now()
    if passed:
        problem = await ProblemRepository(db).get_by_id(verification.problem_id)
        if problem is not None:
            # 验题与晋升解耦：通过仅打「已验待生效」标记，晋升由管理角色显式 apply
            
            problem.pending_verified = True
            problem.case_status = derive_case_status(problem)
            problem.verified_by = verifier_id
            problem.verified_at = datetime.now()
            problem.updated_at = datetime.now()
    # 验题结束（通过 / 失败）后回收邀请链接，避免悬挂失效链接
    token = await redis_get(f"{VERIFY_INVITE_PROBLEM_PREFIX}{verification.problem_id}")
    if token:
        await redis_delete(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
        await redis_delete(f"{VERIFY_INVITE_PROBLEM_PREFIX}{verification.problem_id}")
    await db.flush()
