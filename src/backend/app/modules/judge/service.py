"""题库与判题业务逻辑（docs/contracts/problems.md / judge.md）。

权限约定（docs/contracts/problems.md 端点表）：
- 题目管理角色 = admin / tutor / team_creator（team_admin 为团队域角色，随 teams 模块接入）
- 越权统一抛 2003（docs/contracts/common.md：2003 覆盖资源级越权）
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.judge.models import (
    Problem,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    ProblemVerificationInvite,
    SandboxConfig,
    Submission,
    SubmissionTestCaseResult,
    TestCase,
)
from app.modules.judge.schemas import (
    ProblemCreate,
    ProblemQuery,
    ProblemUpdate,
    SubmissionCreate,
    SubmissionQuery,
    TestCasesUpdate,
    VerifyRequest,
)
from app.modules.users.models import User
from app.shared.common.errors import (
    APIError,
    AUTH_FORBIDDEN,
    PARAM_FORMAT_INVALID,
    RATE_LIMITED,
    RATE_SEND_TOO_FREQUENT,
    RESOURCE_DUPLICATE,
    RESOURCE_NOT_FOUND,
    RESOURCE_STATE_CONFLICT,
    SYSTEM_UPSTREAM_FAILURE,
)
from app.shared.auth.permissions import MANAGER_ROLE_CODES, is_manager as _is_manager
from app.shared.infra.storage import get_storage

_ALLOWED_LANGUAGES = {"python3.12", "cpp17", "java21"}


class ProblemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- 权限 ----

    async def is_manager(self, user: User) -> bool:
        return await _is_manager(self.db, user)

    async def can_manage(self, user: User, problem: Problem) -> bool:
        return problem.owner_id == user.id or await self.is_manager(user)

    async def require_manage(self, user: User, problem: Problem) -> None:
        if not await self.can_manage(user, problem):
            raise APIError(AUTH_FORBIDDEN, "无权限管理该题目", 403)

    # ---- 查询 ----

    async def get(self, problem_id: uuid.UUID) -> Problem:
        problem = await self.db.get(Problem, problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        return problem

    async def list_published(self, query: ProblemQuery, viewer: User | None = None) -> tuple[list[Problem], int]:
        """题库列表：scope=all 仅 published+public；scope=mine 为创建者/管理角色的管理视图。"""
        conditions = []
        if query.scope == "mine":
            if viewer is not None and not await self.is_manager(viewer):
                conditions.append(Problem.owner_id == viewer.id)
            # 管理角色可管理范围内全量（与 require_manage 语义一致）
            if query.status:
                conditions.append(Problem.status == query.status)
        else:
            conditions.extend([Problem.status == "published", Problem.visibility == "public"])
        if query.difficulty:
            conditions.append(Problem.difficulty == query.difficulty)
        if query.keyword:
            conditions.append(Problem.title.ilike(f"%{query.keyword}%"))
        if query.tag:
            conditions.append(
                Problem.id.in_(
                    select(ProblemTagRelation.problem_id)
                    .join(ProblemTag, ProblemTag.id == ProblemTagRelation.tag_id)
                    .where(ProblemTag.name == query.tag)
                )
            )
        total = (
            await self.db.scalar(select(func.count()).select_from(Problem).where(*conditions))
        ) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Problem)
                    .where(*conditions)
                    .order_by(Problem.created_at.desc())
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def _samples(self, problem_id: uuid.UUID) -> list[dict]:
        rows = list(
            (
                await self.db.execute(
                    select(TestCase)
                    .where(TestCase.problem_id == problem_id, TestCase.is_sample.is_(True))
                    .order_by(TestCase.sort_order, TestCase.created_at)
                )
            ).scalars()
        )
        return [
            {"id": str(row.id), "name": row.name or f"sample{index}", "input": row.sample_input or "", "output": row.sample_output or ""}
            for index, row in enumerate(rows, start=1)
        ]

    async def _tag_names(self, problem_id: uuid.UUID) -> list[str]:
        return list(
            (
                await self.db.execute(
                    select(ProblemTag.name)
                    .join(ProblemTagRelation, ProblemTagRelation.tag_id == ProblemTag.id)
                    .where(ProblemTagRelation.problem_id == problem_id)
                    .order_by(ProblemTag.name)
                )
            ).scalars()
        )

    @staticmethod
    async def _read_text(object_key: str | None, limit_bytes: int = 2 * 1024 * 1024) -> str | None:
        """内部读取对象存储文本；存储不可用时返回 None，不影响主流程。"""
        if not object_key:
            return None
        try:
            content, _ = await get_storage().get_bytes(object_key)
            return content[:limit_bytes].decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 存储读取失败降级为无内容
            return None

    async def get_detail(self, problem_id: uuid.UUID, viewer: User | None) -> dict:
        """题目详情：按 status + visibility 过滤访问；管理角色额外可读测试点内容与题解。"""
        problem = await self.get(problem_id)
        manager = viewer is not None and await self.can_manage(viewer, problem)
        publicly_visible = problem.status == "published" and problem.visibility == "public"
        if not publicly_visible and not manager:
            raise APIError(AUTH_FORBIDDEN, "题目不可见", 403)

        detail: dict = {
            "problem": problem,
            "samples": await self._samples(problem.id),
            "tags": await self._tag_names(problem.id),
            "can_manage": manager,
            "test_cases": None,
        }
        if manager:
            cases = list(
                (
                    await self.db.execute(
                        select(TestCase).where(TestCase.problem_id == problem_id).order_by(TestCase.sort_order, TestCase.created_at)
                    )
                ).scalars()
            )
            detail["test_cases"] = [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "is_sample": row.is_sample,
                    "score": row.score,
                    "sort_order": row.sort_order,
                    "input": (row.sample_input if row.is_sample else None) or await self._read_text(row.input_oss_id),
                    "expected_output": (row.sample_output if row.is_sample else None) or await self._read_text(row.expected_output_oss_id),
                }
                for row in cases
            ]
        return detail

    # ---- 写入 ----

    async def create(self, owner: User, body: ProblemCreate) -> Problem:
        if not await self.is_manager(owner):
            raise APIError(AUTH_FORBIDDEN, "无权限创建题目", 403)
        if body.spj and not body.spj_code:
            raise APIError(PARAM_FORMAT_INVALID, "SPJ 题目必须提供 checker 对象引用", 400)
        data = body.model_dump()
        problem = Problem(owner_id=owner.id, status="draft", **data)
        self.db.add(problem)
        await self.db.flush()
        return problem

    async def update(self, user: User, problem_id: uuid.UUID, body: ProblemUpdate) -> Problem:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑", 409)
        changes = body.model_dump(exclude_none=True)
        effective_spj = changes.get("spj", problem.spj)
        effective_spj_code = changes.get("spj_code", problem.spj_code)
        if effective_spj and not effective_spj_code:
            raise APIError(PARAM_FORMAT_INVALID, "SPJ 题目必须提供 checker 对象引用", 400)
        for key, value in changes.items():
            setattr(problem, key, value)
        await self.db.flush()
        return problem

    async def replace_cases(self, user: User, problem_id: uuid.UUID, body: TestCasesUpdate) -> None:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)
        if sum(item.score for item in body.cases if not item.is_sample) != 100:
            raise APIError(PARAM_FORMAT_INVALID, "正式测试点分值总和必须为 100", 400)
        old_rows = list((await self.db.scalars(select(TestCase).where(TestCase.problem_id == problem_id))).all())
        try:
            storage = get_storage() if any(not item.is_sample for item in body.cases) or any(row.input_oss_id or row.expected_output_oss_id for row in old_rows) else None
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc
        created_keys: list[str] = []
        new_rows: list[TestCase] = []
        try:
            for index, item in enumerate(body.cases, start=1):
                if not item.input and not item.expected_output:
                    raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                row_data = {"name": item.name or str(index), "is_sample": item.is_sample, "score": item.score, "sort_order": item.sort_order or index}
                if item.is_sample:
                    # 样例仅存库用于展示与自测，不参与正式判题（2026-08-15-sample-not-judged）
                    row_data.update(sample_input=item.input, sample_output=item.expected_output, input_oss_id=None, expected_output_oss_id=None)
                else:
                    input_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/input"
                    output_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/output"
                    assert storage is not None
                    await storage.put_bytes(input_key, item.input.encode("utf-8"), "text/plain; charset=utf-8")
                    await storage.put_bytes(output_key, item.expected_output.encode("utf-8"), "text/plain; charset=utf-8")
                    created_keys.extend([input_key, output_key])
                    row_data.update(sample_input=None, sample_output=None, input_oss_id=input_key, expected_output_oss_id=output_key)
                new_rows.append(TestCase(problem_id=problem_id, **row_data))
            await self.db.execute(delete(TestCase).where(TestCase.problem_id == problem_id))
            self.db.add_all(new_rows)
            await self.db.flush()
        except Exception as exc:
            for key in created_keys:
                try:
                    if storage is not None:
                        await storage.delete(key)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc
        for row in old_rows:
            for key in (row.input_oss_id, row.expected_output_oss_id):
                if key and storage is not None:
                    try:
                        await storage.delete(key)
                    except Exception:
                        pass

    # ---- 生命周期 ----

    async def publish(self, user: User, problem_id: uuid.UUID) -> Problem:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "published":
            raise APIError(RESOURCE_STATE_CONFLICT, "题目已发布", 409)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可发布", 409)
        if not problem.is_verified:
            raise APIError(RESOURCE_STATE_CONFLICT, "发布前须验题通过", 409)
        formal_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(TestCase)
                .where(TestCase.problem_id == problem_id, TestCase.is_sample.is_(False))
            )
        ) or 0
        if formal_count == 0:
            raise APIError(RESOURCE_STATE_CONFLICT, "发布前须配置至少一个正式测试点", 409)
        problem.status = "published"
        problem.published_at = datetime.now()
        await self.db.flush()
        return problem

    async def archive(self, user: User, problem_id: uuid.UUID) -> Problem:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "题目已归档", 409)
        problem.status = "archived"
        await self.db.flush()
        return problem

    async def promote(self, user: User, problem_id: uuid.UUID) -> Problem:
        """团队题目升级公开（不可逆）；teams 模块上线前所有题目均为全站题目。"""
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        raise APIError(RESOURCE_STATE_CONFLICT, "仅团队题目可升级公开", 409)

    # ---- 验题 ----

    async def init_verification(self, user: User, problem_id: uuid.UUID, body: VerifyRequest) -> dict:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        pending = await self.db.scalar(
            select(ProblemVerification).where(
                ProblemVerification.problem_id == problem_id, ProblemVerification.status == "pending"
            )
        )
        if pending is not None:
            raise APIError(RESOURCE_DUPLICATE, "已有进行中的验题", 409)

        invite = None
        verifier_id = body.verifier_id
        if body.invite_expires_hours is not None:
            invite = ProblemVerificationInvite(
                problem_id=problem_id,
                token=secrets.token_urlsafe(32)[:64],
                invited_by=user.id,
                expires_at=datetime.now() + timedelta(hours=body.invite_expires_hours),
            )
            self.db.add(invite)
            await self.db.flush()
            verifier_id = None
        elif verifier_id is not None and await self.db.get(User, verifier_id) is None:
            raise APIError(RESOURCE_NOT_FOUND, "受邀验题人不存在", 404)

        verification = ProblemVerification(problem_id=problem_id, verifier_id=verifier_id, invite_id=invite.id if invite else None)
        self.db.add(verification)
        await self.db.flush()
        result = {"verification_id": str(verification.id)}
        if invite is not None:
            result["invite"] = {"token": invite.token, "expires_at": invite.expires_at.isoformat() if invite.expires_at else None}
        if verification.verifier_id:
            result["verifier_id"] = str(verification.verifier_id)
        return result

    async def resolve_invite(self, token: str) -> dict:
        invite = await self.db.scalar(select(ProblemVerificationInvite).where(ProblemVerificationInvite.token == token))
        if invite is None:
            raise APIError(RESOURCE_NOT_FOUND, "邀请链接无效", 404)
        expired = invite.expires_at is not None and invite.expires_at < datetime.now(invite.expires_at.tzinfo)
        if invite.status != "active" or expired:
            raise APIError(RESOURCE_STATE_CONFLICT, "邀请链接已失效", 409)
        problem = await self.get(invite.problem_id)
        return {"problem_id": str(problem.id), "problem_title": problem.title, "expires_at": invite.expires_at.isoformat() if invite.expires_at else None}

    async def submit_verification(self, user: User, problem_id: uuid.UUID, body: VerifyRequest) -> Submission:
        assert body.code is not None and body.language is not None  # schema 已校验
        if body.language not in _ALLOWED_LANGUAGES:
            raise APIError(PARAM_FORMAT_INVALID, "语言不在白名单", 400)
        problem = await self.get(problem_id)
        verification = await self.db.scalar(
            select(ProblemVerification)
            .where(ProblemVerification.problem_id == problem_id, ProblemVerification.status == "pending")
            .order_by(ProblemVerification.created_at.desc())
        )
        if verification is None:
            raise APIError(RESOURCE_NOT_FOUND, "该题目没有进行中的验题", 404)

        if body.invite_token:
            invite = await self.db.scalar(
                select(ProblemVerificationInvite).where(ProblemVerificationInvite.token == body.invite_token)
            )
            if invite is None or invite.problem_id != problem_id or invite.status != "active":
                raise APIError(AUTH_FORBIDDEN, "验题邀请无效", 403)
            if invite.expires_at is not None and invite.expires_at < datetime.now(invite.expires_at.tzinfo):
                raise APIError(AUTH_FORBIDDEN, "验题邀请已过期", 403)
            if verification.invite_id != invite.id:
                raise APIError(AUTH_FORBIDDEN, "验题邀请与当前验题记录不匹配", 403)
        elif verification.verifier_id != user.id:
            raise APIError(AUTH_FORBIDDEN, "只有受邀验题人可以提交验题", 403)

        submission = Submission(
            user_id=user.id,
            problem_id=problem_id,
            verification_id=verification.id,
            language=body.language,
            code=body.code,
            submit_type="verify",
        )
        self.db.add(submission)
        verification.language = body.language
        verification.code = body.code
        await self.db.flush()
        return submission


class SubmissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _can_access_problem(self, user: User, problem: Problem) -> bool:
        if problem.status == "published" and problem.visibility == "public":
            return True
        return await ProblemService(self.db).can_manage(user, problem)

    async def _language_enabled(self, language: str) -> bool:
        """语言白名单来自 sandbox_configs 且启用（docs/contracts/judge.md 提交校验）。"""
        config = await self.db.scalar(select(SandboxConfig).where(SandboxConfig.language == language))
        if config is not None:
            return config.is_enabled
        return language in _ALLOWED_LANGUAGES  # 配置缺失时兜底

    @staticmethod
    def _system_int(configs: dict[str, Any], key: str, default: int) -> int:
        try:
            return int(configs.get(key, default))
        except (TypeError, ValueError):
            return default

    async def _check_rate_limits(self, user: User, problem_id: uuid.UUID) -> None:
        """提交冷却（4001）与全局并发上限（4002），阈值取系统配置 sandbox 域。"""
        from app.modules.admin.models import SystemConfig
        from app.modules.judge.dispatcher import active_judge_count
        from app.shared.infra.redis import get_redis

        rows = (
            await self.db.execute(select(SystemConfig).where(SystemConfig.category == "sandbox"))
        ).scalars().all()
        configs = {row.config_key: row.config_value for row in rows}
        cooldown = max(0, self._system_int(configs, "sandbox.cooldown_seconds", 10))
        if cooldown > 0:
            r = get_redis()
            key = f"judge:cooldown:{user.id}:{problem_id}"
            set_ok = await r.set(key, "1", ex=cooldown, nx=True)
            if not set_ok:
                raise APIError(RATE_SEND_TOO_FREQUENT, "提交冷却中，请稍后再试", 429)
        concurrency = self._system_int(configs, "sandbox.judge_concurrency", 8)
        if concurrency > 0 and await active_judge_count() >= concurrency:
            raise APIError(RATE_LIMITED, "判题并发已达上限，请稍后再试", 429)

    async def create(self, user: User, body: SubmissionCreate) -> Submission:
        problem = await self.db.get(Problem, body.problem_id)
        if problem is None:
            raise APIError(RESOURCE_NOT_FOUND, "题目不存在", 404)
        if not await self._can_access_problem(user, problem):
            raise APIError(AUTH_FORBIDDEN, "题目不可见", 403)
        if not await self._language_enabled(body.language):
            raise APIError(PARAM_FORMAT_INVALID, "语言不在白名单", 400)
        await self._check_rate_limits(user, body.problem_id)
        submission = Submission(user_id=user.id, problem_id=body.problem_id, language=body.language, code=body.code, submit_type="practice")
        self.db.add(submission)
        await self.db.flush()
        return submission

    async def list_for_user(self, user: User, query: SubmissionQuery) -> tuple[list[Submission], int]:
        conditions = [Submission.user_id == user.id]
        if query.problem_id:
            conditions.append(Submission.problem_id == query.problem_id)
        if query.status:
            conditions.append(Submission.status == query.status)
        total = (await self.db.scalar(select(func.count()).select_from(Submission).where(*conditions))) or 0
        rows = list(
            (
                await self.db.execute(
                    select(Submission)
                    .where(*conditions)
                    .order_by(Submission.created_at.desc())
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
            ).scalars()
        )
        return rows, int(total)

    async def get_detail(self, user: User, submission_id: uuid.UUID) -> dict:
        """提交详情（owner 可见）：含逐测试点结果；不返回期望输出。"""
        submission = await self.db.scalar(
            select(Submission).where(Submission.id == submission_id, Submission.user_id == user.id)
        )
        if submission is None:
            raise APIError(RESOURCE_NOT_FOUND, "提交不存在", 404)
        rows = list(
            (
                await self.db.execute(
                    select(SubmissionTestCaseResult, TestCase.name, TestCase.sort_order)
                    .join(TestCase, TestCase.id == SubmissionTestCaseResult.test_case_id)
                    .where(SubmissionTestCaseResult.submission_id == submission_id)
                    .order_by(TestCase.sort_order, TestCase.created_at)
                )
            ).all()
        )
        cases = []
        for result, case_name, _sort in rows:
            output_text = None
            if result.output:
                try:
                    content, _ = await get_storage().get_bytes(result.output)
                    output_text = content[:8192].decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001 - 输出读取失败不阻塞详情
                    output_text = None
            cases.append(
                {
                    "id": str(result.id),
                    "case_name": case_name,
                    "status": result.status,
                    "time_used_ms": result.time_used_ms,
                    "memory_used_kb": result.memory_used_kb,
                    "score": result.score,
                    "output": output_text,
                }
            )
        return {
            "submission": submission,
            "cases": cases,
        }


async def finalize_verify_submission(db: AsyncSession, submission: Submission) -> None:
    """验题判题完成后的回写（由 Judge Worker 在 finish_submission 之后调用）。

    - 通过 → problem_verifications.status='passed'，回写 problems.is_verified / verified_by / verified_at
    - 未通过 → problem_verifications.status='failed'
    """
    if submission.submit_type != "verify" or not submission.verification_id:
        return
    verification = await db.get(ProblemVerification, submission.verification_id)
    problem = await db.get(Problem, submission.problem_id)
    if verification is None or problem is None:
        return
    passed = submission.status == "accepted"
    verification.status = "passed" if passed else "failed"
    if passed:
        problem.is_verified = True
        problem.verified_by = submission.user_id
        problem.verified_at = datetime.now()
