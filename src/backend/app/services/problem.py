"""题库域服务：题目生命周期、标签、验题、测试点管理。"""
from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
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
from app.core.redis import get_redis, redis_get_json, redis_set_json
from app.core.storage import get_storage
from app.core.dependency import is_manager
from app.models.problem import (
    Problem,
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
    ProblemQuery,
    ProblemUpdate,
    SampleOut,
    SamplesUpdate,
    TestCaseOut,
    TestCasesPatch,
    TestCasesUpdate,
    VerificationInitOut,
    VerificationInviteOut,
)

logger = logging.getLogger(__name__)

VERIFY_INVITE_KEY_PREFIX = "verify_invite:"


@dataclass(frozen=True)
class ProblemDetailData:
    """题目详情装配结果：get_detail → 路由 _detail 的进程内传输结构。"""

    problem: Problem
    samples: list[SampleOut]
    tags: list[str]
    can_manage: bool
    needs_reverification: bool
    test_cases: list[TestCaseOut] | None
    cases_updated_at: datetime | None


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

    loop = asyncio.get_event_loop()
    loop.create_task(_cleanup(stale_keys))


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
        manager = viewer is not None and await is_manager(self.db, viewer)
        return await self.problems.list_published(query, viewer_id, manager)

    async def verification_flags(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, bool]:
        """返回 {problem_id: needs_reverification} 用于 scope=mine 列表。"""
        if not problem_ids:
            return {}
        tc_max = (
            select(
                TestCase.problem_id,
                func.max(TestCase.updated_at).label("cases_max"),
            )
            .where(TestCase.problem_id.in_(problem_ids))
            .group_by(TestCase.problem_id)
            .subquery()
        )
        rows = (
            await self.db.execute(
                select(
                    Problem.id,
                    Problem.verified_at,
                    Problem.samples_updated_at,
                    tc_max.c.cases_max,
                )
                .outerjoin(tc_max, Problem.id == tc_max.c.problem_id)
                .where(Problem.id.in_(problem_ids))
            )
        ).all()
        flags: dict[uuid.UUID, bool] = {}
        for row in rows:
            verified_at = row.verified_at
            if verified_at is None:
                flags[row.id] = True
                continue
            latest_content = max(
                (row.cases_max or datetime.min, row.samples_updated_at or datetime.min),
            )
            flags[row.id] = latest_content > verified_at
        return flags

    async def create(self, user: object, body: ProblemCreate) -> Problem:
        if not await is_manager(self.db, user):
            raise APIError(AUTH_FORBIDDEN, "无权限：需要管理角色", 403)
        problem = Problem(
            title=body.title,
            description=body.description,
            input_description=body.input_description,
            output_description=body.output_description,
            solution=body.solution,
            visibility=body.visibility,
            time_limit_ms=body.time_limit_ms,
            memory_limit_mb=body.memory_limit_mb,
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
        formal_count = await self.problems.count_formal_cases(problem_id)
        cases_updated_at = await self.problems.max_cases_updated_at(problem_id)
        needs_reverification = False
        if problem.verified_at and problem.is_verified:
            latest_content = max(
                (cases_updated_at or datetime.min, problem.samples_updated_at or datetime.min),
            )
            needs_reverification = latest_content > problem.verified_at
        test_cases = None
        if can_manage:
            # 管理角色编辑用：回读内容而非对象 key（docs/contracts/problems.md）
            test_cases = await self.list_cases_with_contents(problem_id)
        return ProblemDetailData(
            problem=problem,
            samples=samples,
            tags=tag_names,
            can_manage=can_manage,
            needs_reverification=needs_reverification,
            test_cases=test_cases,
            cases_updated_at=cases_updated_at,
        )

    @staticmethod
    def _samples_view(problem: Problem) -> list[SampleOut]:
        """problems.samples JSONB → 展示结构（name 按序派生，不暴露内部 id）。"""
        return [
            SampleOut(name=f"sample{index}", input=item.get("input") or "", output=item.get("output") or "")
            for index, item in enumerate(problem.samples or [], start=1)
            if isinstance(item, dict)
        ]

    async def update(self, user: object, problem_id: uuid.UUID, body: ProblemUpdate) -> Problem:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑", 409)
        if body.title is not None:
            problem.title = body.title
        if body.description is not None:
            problem.description = body.description
        if body.input_description is not None:
            problem.input_description = body.input_description
        if body.output_description is not None:
            problem.output_description = body.output_description
        if body.solution is not None:
            problem.solution = body.solution
        if body.visibility is not None:
            problem.visibility = body.visibility
        if body.time_limit_ms is not None:
            problem.time_limit_ms = body.time_limit_ms
        if body.memory_limit_mb is not None:
            problem.memory_limit_mb = body.memory_limit_mb
        if body.tags is not None:
            await self._sync_tags(problem.id, body.tags)
        problem.updated_at = datetime.now()
        await self.db.flush()
        return problem

    async def replace_cases(self, user: object, problem_id: uuid.UUID, body: TestCasesUpdate) -> list[str]:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)
        old_keys = await self.problems.get_old_test_case_keys(problem_id)
        await self.problems.delete_test_cases(problem_id)
        try:
            storage = get_storage()
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc
        uploaded: list[tuple[str, str, TestCase]] = []
        try:
            for idx, item in enumerate(body.cases):
                if not item.input and not item.expected_output:
                    raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                input_content = item.input.encode("utf-8")
                output_content = item.expected_output.encode("utf-8")
                input_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/input"
                output_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/output"
                await storage.put_bytes(input_key, input_content, "text/plain; charset=utf-8")
                await storage.put_bytes(output_key, output_content, "text/plain; charset=utf-8")
                uploaded.append((input_key, output_key, TestCase(
                    problem_id=problem_id,
                    name=item.name or str(idx + 1),
                    input_oss_id=input_key,
                    expected_output_oss_id=output_key,
                    sort_order=item.sort_order or idx + 1,
                )))
        except Exception as exc:
            for input_key, output_key, _ in uploaded:
                for key in (input_key, output_key):
                    try:
                        await storage.delete(key)
                    except Exception:
                        pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc
        await self.problems.add_test_cases([row for _, _, row in uploaded])
        return old_keys

    async def list_cases_with_contents(self, problem_id: uuid.UUID) -> list[TestCaseOut]:
        """管理角色编辑用：回读测试点内容（docs/contracts/problems.md 管理角色读详情）。"""
        storage = get_storage()
        out: list[TestCaseOut] = []
        for tc in await self.test_cases.list_formal_cases(problem_id):
            input_text = expected_text = None
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
            ))
        return out

    async def patch_cases(self, user: object, problem_id: uuid.UUID, body: TestCasesPatch) -> list[str]:
        """增量更新测试点（PATCH /problems/{id}/test-cases）：只改动提交的行。

        - upserts 带 id：改名 / 调序 / 换内容（内容留空 = 保持不变），仅变更行 bump updated_at
          （未动行不触发「需重新验题」与判题节点 data_version 缓存失效）
        - upserts 不带 id：新增
        - delete_ids：删除（历史判题结果保留，test_case_id 由 ON DELETE SET NULL 置空）
        返回需异步清理的 MinIO 旧对象 key。
        """
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)

        existing = {tc.id: tc for tc in await self.test_cases.list_formal_cases(problem_id)}
        upsert_ids = [item.id for item in body.upserts if item.id is not None]
        if len(upsert_ids) != len(set(upsert_ids)):
            raise APIError(PARAM_FORMAT_INVALID, "同一测试点被重复更新", 400)
        overlap = set(upsert_ids) & set(body.delete_ids)
        if overlap:
            raise APIError(PARAM_FORMAT_INVALID, "测试点不能同时更新和删除", 400)
        unknown = [cid for cid in upsert_ids + body.delete_ids if cid not in existing]
        if unknown:
            raise APIError(RESOURCE_NOT_FOUND, "测试点不存在", 404)
        try:
            storage = get_storage()
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc

        stale_keys: list[str] = []
        uploaded_keys: list[tuple[uuid.UUID, str]] = []

        async def _put_content(case_pk: uuid.UUID, kind: str, content: str) -> str:
            key = f"problems/{problem_id}/cases/{uuid.uuid4()}/{'input' if kind == 'input' else 'output'}"
            await storage.put_bytes(key, content.encode("utf-8"), "text/plain; charset=utf-8")
            uploaded_keys.append((case_pk, key))
            return key

        try:
            for index, item in enumerate(body.upserts):
                if item.id is None:
                    if not item.input.strip() and not item.expected_output.strip():
                        raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                    row = TestCase(
                        problem_id=problem_id,
                        name=item.name or str(index + 1),
                        input_oss_id=None,
                        expected_output_oss_id=None,
                        sort_order=item.sort_order or index + 1,
                    )
                    self.db.add(row)
                    await self.db.flush()
                    if item.input.strip():
                        row.input_oss_id = await _put_content(row.id, "input", item.input)
                    if item.expected_output.strip():
                        row.expected_output_oss_id = await _put_content(row.id, "output", item.expected_output)
                    continue
                row = existing[item.id]
                changed = False
                if item.name is not None and item.name != row.name:
                    row.name = item.name
                    changed = True
                if item.sort_order and item.sort_order != row.sort_order:
                    row.sort_order = item.sort_order
                    changed = True
                for field in ("input", "expected_output"):
                    content = getattr(item, field)
                    if content.strip():
                        oss_field = "input_oss_id" if field == "input" else "expected_output_oss_id"
                        stale_keys.append(getattr(row, oss_field))
                        setattr(row, oss_field, await _put_content(row.id, field, content))
                        changed = True
                if changed:
                    row.updated_at = datetime.now()
            rows_to_delete = [existing[cid] for cid in body.delete_ids]
            for row in rows_to_delete:
                stale_keys.extend(key for key in (row.input_oss_id, row.expected_output_oss_id) if key)
            await self.test_cases.delete_cases(rows_to_delete)
            await self.db.flush()
        except Exception as exc:
            for _, key in uploaded_keys:
                try:
                    await storage.delete(key)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc
        return [key for key in stale_keys if key]

    async def replace_samples(self, user: object, problem_id: uuid.UUID, body: SamplesUpdate) -> None:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑样例", 409)
        problem.samples = [s.model_dump() for s in body.samples]
        problem.samples_updated_at = datetime.now()
        problem.updated_at = datetime.now()
        await self.db.flush()

    async def publish(self, user: object, problem_id: uuid.UUID) -> Problem:
        problem = await self._require_manage(user, problem_id)
        if problem.status == ProblemStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "已归档题目不可发布", 409)
        if not problem.is_verified:
            raise APIError(RESOURCE_STATE_CONFLICT, "题目未验题，不可发布", 409)
        formal_count = await self.problems.count_formal_cases(problem_id)
        if formal_count == 0:
            raise APIError(RESOURCE_STATE_CONFLICT, "题目无正式测试点，不可发布", 409)
        cases_updated_at = await self.problems.max_cases_updated_at(problem_id)
        if problem.verified_at and cases_updated_at and cases_updated_at > problem.verified_at:
            raise APIError(RESOURCE_STATE_CONFLICT, "测试点在验题通过后被修改，请重新验题", 409)
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

    async def init_verification(self, user: object, problem_id: uuid.UUID, invite_expires_hours: int | None) -> VerificationInitOut:
        problem = await self.problems.get_by_id(problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await _can_manage(self.db, user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限", 403)
        pending = await self.verifications.get_pending(problem_id)
        if pending is not None:
            raise APIError(RESOURCE_DUPLICATE, "已有进行中的验题", 409)
        verification = ProblemVerification(problem_id=problem_id)
        verification = await self.verifications.create(verification)
        invite = None
        if invite_expires_hours is not None:
            token = secrets.token_urlsafe(32)[:64]
            ttl_seconds = int(invite_expires_hours * 3600)
            await redis_set_json(
                f"{VERIFY_INVITE_KEY_PREFIX}{token}",
                {"problem_id": str(problem_id)},
                ttl_seconds=ttl_seconds,
            )
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            invite = {"token": token, "expires_at": expires_at.isoformat()}
        return VerificationInitOut(verification_id=str(verification.id), invite=invite)

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
            expires_at=(datetime.now() + timedelta(seconds=remaining)).isoformat()
            if isinstance(remaining, int) and remaining > 0
            else None,
            description=problem.description,
            input_description=problem.input_description,
            output_description=problem.output_description,
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
    if await is_manager(db, user):
        return True
    return problem.owner_id == user.id


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


async def list_formal_cases(db: AsyncSession, problem_id: uuid.UUID) -> list[TestCase]:
    return await TestCaseRepository(db).list_formal_cases(problem_id)


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
            problem.is_verified = True
            problem.verified_by = verifier_id
            problem.verified_at = datetime.now()
            problem.updated_at = datetime.now()
    await db.flush()
