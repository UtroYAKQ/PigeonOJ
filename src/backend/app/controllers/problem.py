"""题库业务逻辑（docs/contracts/problems.md）。

权限约定（docs/contracts/problems.md 端点表）：
- 题目管理角色 = admin / tutor / team_creator（team_admin 为团队域角色，随 teams 模块接入）
- 越权统一抛 2003（docs/contracts/common.md：2003 覆盖资源级越权）

样例与测试点分离：样例存 problems.samples JSONB（仅展示），测试点全部为正式判题数据。
验题邀请链接存 Redis（verify_invite:{token}，TTL 即有效期，不落库）。

模块级函数（get_pending_validation 等）是供 judge 模块经 api.py 调用的钩子：
判题链路创建 / 回写验题提交时，验题状态机仍由题库模块持有。
"""
from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.problem import (
    Problem,
    ProblemTag,
    ProblemTagRelation,
    ProblemVerification,
    TestCase,
)
from app.schemas.problem import (
    ProblemCreate,
    ProblemQuery,
    ProblemUpdate,
    SamplesUpdate,
    TestCasesUpdate,
)
from app.models.user import User
from app.core.dependency import is_manager as _is_manager
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

VERIFY_INVITE_KEY_PREFIX = "verify_invite:"


def schedule_object_cleanup(keys: list[str]) -> None:
    """异步清理不再被引用的 MinIO 对象；失败不阻塞主流程（fire-and-forget）。"""

    async def _cleanup() -> None:
        for key in keys:
            try:
                await get_storage().delete(key)
            except Exception:  # noqa: BLE001 - 清理失败留待人工或后续任务处理
                pass

    if keys:
        asyncio.create_task(_cleanup())


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

    @staticmethod
    def _samples_view(problem: Problem) -> list[dict]:
        """problems.samples JSONB → 展示结构（name 按序派生，不暴露内部 id）。"""
        return [
            {"name": f"sample{index}", "input": item.get("input") or "", "output": item.get("output") or ""}
            for index, item in enumerate(problem.samples or [], start=1)
            if isinstance(item, dict)
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

    async def _apply_tags(self, problem_id: uuid.UUID, names: list[str]) -> None:
        """全量替换题目标签关联；仅接受激活标签名（docs/contracts/problems.md 标签节）。"""
        await self.db.execute(delete(ProblemTagRelation).where(ProblemTagRelation.problem_id == problem_id))
        if not names:
            return
        rows = list(
            (await self.db.execute(select(ProblemTag).where(ProblemTag.name.in_(names)))).scalars()
        )
        by_name = {row.name: row for row in rows}
        missing = [name for name in names if name not in by_name]
        if missing:
            raise APIError(PARAM_FORMAT_INVALID, f"标签不存在：{', '.join(missing)}", 400)
        archived = [row.name for row in rows if row.status != "active"]
        if archived:
            raise APIError(PARAM_FORMAT_INVALID, f"标签已归档：{', '.join(archived)}", 400)
        for name in names:
            self.db.add(ProblemTagRelation(problem_id=problem_id, tag_id=by_name[name].id))
        await self.db.flush()

    @staticmethod
    def _needs_reverification(
        is_verified: bool,
        verified_at: datetime | None,
        cases_updated_at: datetime | None,
        samples_updated_at: datetime | None = None,
    ) -> bool:
        """验题状态判定：未验题，或测试点 / 样例晚于最近验题通过时间变更 → 须重新验题。"""
        if not is_verified:
            return True
        if verified_at is None:
            return False
        for changed_at in (cases_updated_at, samples_updated_at):
            if changed_at is not None and changed_at > verified_at:
                return True
        return False

    async def verification_flags(self, problem_ids: list[uuid.UUID]) -> dict[uuid.UUID, bool]:
        """批量计算 needs_reverification（scope=mine 管理列表使用）。"""
        if not problem_ids:
            return {}
        rows = (
            await self.db.execute(
                select(
                    Problem.id,
                    Problem.is_verified,
                    Problem.verified_at,
                    Problem.samples_updated_at,
                    func.max(TestCase.updated_at),
                )
                .outerjoin(TestCase, TestCase.problem_id == Problem.id)
                .where(Problem.id.in_(problem_ids))
                .group_by(Problem.id, Problem.is_verified, Problem.verified_at, Problem.samples_updated_at)
            )
        ).all()
        return {
            pid: self._needs_reverification(is_verified, verified_at, max_case_updated, samples_updated_at)
            for pid, is_verified, verified_at, samples_updated_at, max_case_updated in rows
        }

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

    async def _cases_updated_at(self, problem_id: uuid.UUID) -> datetime | None:
        """测试点最近一次更新时间；无任何测试点时为 None。"""
        return await self.db.scalar(
            select(func.max(TestCase.updated_at)).where(TestCase.problem_id == problem_id)
        )

    async def get_detail(self, problem_id: uuid.UUID, viewer: User | None) -> dict:
        """题目详情：按 status + visibility 过滤访问；管理角色额外可读测试点内容与题解。"""
        problem = await self.get(problem_id)
        manager = viewer is not None and await self.can_manage(viewer, problem)
        publicly_visible = problem.status == "published" and problem.visibility == "public"
        if not publicly_visible and not manager:
            raise APIError(AUTH_FORBIDDEN, "题目不可见", 403)

        cases_updated_at = await self._cases_updated_at(problem_id)
        detail: dict = {
            "problem": problem,
            "samples": self._samples_view(problem),
            "tags": await self._tag_names(problem.id),
            "can_manage": manager,
            "test_cases": None,
            "cases_updated_at": cases_updated_at,
            "needs_reverification": self._needs_reverification(
                problem.is_verified, problem.verified_at, cases_updated_at, problem.samples_updated_at
            ),
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
                    "sort_order": row.sort_order,
                    "input": await self._read_text(row.input_oss_id),
                    "expected_output": await self._read_text(row.expected_output_oss_id),
                }
                for row in cases
            ]
        return detail

    # ---- 写入 ----

    async def create(self, owner: User, body: ProblemCreate) -> Problem:
        if not await self.is_manager(owner):
            raise APIError(AUTH_FORBIDDEN, "无权限创建题目", 403)
        data = body.model_dump(exclude={"tags"})
        problem = Problem(owner_id=owner.id, status="draft", **data)
        self.db.add(problem)
        await self.db.flush()
        await self._apply_tags(problem.id, body.tags)
        return problem

    async def update(self, user: User, problem_id: uuid.UUID, body: ProblemUpdate) -> Problem:
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑", 409)
        changes = body.model_dump(exclude_none=True, exclude={"tags"} if body.tags is not None else set())
        for key, value in changes.items():
            setattr(problem, key, value)
        if body.tags is not None:
            await self._apply_tags(problem_id, body.tags)
        await self.db.flush()
        return problem

    async def replace_cases(self, user: User, problem_id: uuid.UUID, body: TestCasesUpdate) -> list[str]:
        """全量替换正式测试点；返回被替换的旧对象 key 供调用方在提交事务后异步清理。"""
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑测试点", 409)
        old_rows = list((await self.db.scalars(select(TestCase).where(TestCase.problem_id == problem_id))).all())
        stale_keys = [
            key
            for row in old_rows
            for key in (row.input_oss_id, row.expected_output_oss_id)
            if key
        ]
        try:
            storage = get_storage()
        except OSError as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "对象存储服务未配置或不可用", 503) from exc
        created_keys: list[str] = []
        new_rows: list[TestCase] = []
        try:
            for index, item in enumerate(body.cases, start=1):
                if not item.input and not item.expected_output:
                    raise APIError(PARAM_FORMAT_INVALID, "测试点输入和输出不能为空", 400)
                input_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/input"
                output_key = f"problems/{problem_id}/cases/{uuid.uuid4()}/output"
                await storage.put_bytes(input_key, item.input.encode("utf-8"), "text/plain; charset=utf-8")
                await storage.put_bytes(output_key, item.expected_output.encode("utf-8"), "text/plain; charset=utf-8")
                created_keys.extend([input_key, output_key])
                new_rows.append(
                    TestCase(
                        problem_id=problem_id,
                        name=item.name or str(index),
                        sort_order=item.sort_order or index,
                        input_oss_id=input_key,
                        expected_output_oss_id=output_key,
                    )
                )
            await self.db.execute(delete(TestCase).where(TestCase.problem_id == problem_id))
            self.db.add_all(new_rows)
            await self.db.flush()
        except Exception as exc:
            for key in created_keys:
                try:
                    await storage.delete(key)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "测试点上传失败", 503) from exc
        return stale_keys

    async def replace_samples(self, user: User, problem_id: uuid.UUID, body: SamplesUpdate) -> Problem:
        """全量替换展示样例（写 problems.samples，更新 samples_updated_at）。"""
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        if problem.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "归档题目不可编辑样例", 409)
        problem.samples = [{"input": item.input, "output": item.output} for item in body.samples]
        problem.samples_updated_at = datetime.now()
        await self.db.flush()
        return problem

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
        cases_updated_at = await self._cases_updated_at(problem_id)
        if self._needs_reverification(
            problem.is_verified, problem.verified_at, cases_updated_at, problem.samples_updated_at
        ):
            raise APIError(
                RESOURCE_STATE_CONFLICT,
                "测试点或样例在验题通过后已变更，须重新验题后再发布",
                409,
            )
        formal_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(TestCase)
                .where(
                    TestCase.problem_id == problem_id,
                    TestCase.input_oss_id.is_not(None),
                    TestCase.expected_output_oss_id.is_not(None),
                )
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

    # ---- 验题（记录管理；提交入口在 judge 模块） ----

    async def init_verification(self, user: User, problem_id: uuid.UUID, invite_expires_hours) -> dict:
        """发起验题：invite_expires_hours 传值则生成链接邀请（token 存 Redis，TTL 即有效期），
        否则创建空白 pending 记录供出题人 / 管理角色自行验题。"""
        problem = await self.get(problem_id)
        await self.require_manage(user, problem)
        pending = await get_pending_verification(self.db, problem_id)
        if pending is not None:
            raise APIError(RESOURCE_DUPLICATE, "已有进行中的验题", 409)

        invite_token = None
        expires_at = None
        if invite_expires_hours is not None:
            invite_token = secrets.token_urlsafe(32)[:64]
            ttl_seconds = int(invite_expires_hours * 3600)
            await redis_set_json(
                f"{VERIFY_INVITE_KEY_PREFIX}{invite_token}",
                {"problem_id": str(problem_id)},
                ttl_seconds=ttl_seconds,
            )
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        verification = ProblemVerification(problem_id=problem_id)
        self.db.add(verification)
        await self.db.flush()
        result: dict = {"verification_id": str(verification.id)}
        if invite_token is not None:
            result["invite"] = {"token": invite_token, "expires_at": expires_at.isoformat() if expires_at else None}
        return result

    async def resolve_invite(self, token: str) -> dict:
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
        problem = await self.get(problem_id)
        return {
            "problem_id": str(problem.id),
            "problem_title": problem.title,
            "expires_at": (datetime.now() + timedelta(seconds=remaining)).isoformat()
            if isinstance(remaining, int) and remaining > 0
            else None,
            # 邀请页展示题面与样例（不含正式测试点内容 / 题解，受邀人凭代码验题）
            "description": problem.description,
            "input_description": problem.input_description,
            "output_description": problem.output_description,
            "tags": await self._tag_names(problem.id),
            "time_limit_ms": problem.time_limit_ms,
            "memory_limit_mb": problem.memory_limit_mb,
            "samples": self._samples_view(problem),
        }


# ---------------- 供 judge 模块调用的验题钩子（经 api.py 暴露） ----------------


async def get_problem(db: AsyncSession, problem_id: uuid.UUID) -> Problem | None:
    return await db.get(Problem, problem_id)


async def get_test_case(db: AsyncSession, test_case_id: uuid.UUID) -> TestCase | None:
    return await db.get(TestCase, test_case_id)


async def list_formal_cases(db: AsyncSession, problem_id: uuid.UUID) -> list[TestCase]:
    """按判题顺序返回正式测试点（test_cases 表内全部为正式数据）。"""
    return list(
        (
            await db.execute(
                select(TestCase)
                .where(TestCase.problem_id == problem_id)
                .order_by(TestCase.sort_order, TestCase.created_at)
            )
        ).scalars()
    )


async def can_manage_problem(db: AsyncSession, user: User, problem: Problem) -> bool:
    """题目可见性管理判断：owner 或题目管理角色。"""
    return problem.owner_id == user.id or await _is_manager(db, user)


async def get_pending_verification(db: AsyncSession, problem_id: uuid.UUID) -> ProblemVerification | None:
    return await db.scalar(
        select(ProblemVerification).where(
            ProblemVerification.problem_id == problem_id, ProblemVerification.status == "pending"
        )
    )


async def validate_verification_invite(problem_id: uuid.UUID, token: str) -> None:
    """校验验题邀请链接：Redis key 存在且 problem_id 匹配；否则抛 2003。"""
    payload = await redis_get_json(f"{VERIFY_INVITE_KEY_PREFIX}{token}")
    if not isinstance(payload, dict) or payload.get("problem_id") != str(problem_id):
        raise APIError(AUTH_FORBIDDEN, "验题邀请无效", 403)


async def attach_verification_code(db: AsyncSession, verification_id: uuid.UUID, language: str, code: str) -> None:
    """验题提交时把代码快照回写到验题记录。"""
    verification = await db.get(ProblemVerification, verification_id)
    if verification is None:
        return
    verification.language = language
    verification.code = code
    await db.flush()


async def complete_verification(db: AsyncSession, verification_id: uuid.UUID, *, passed: bool, verifier_id) -> None:
    """验题判题完成后的状态回写（由 Judge Worker 在结果落库后调用）。

    - 通过 → problem_verifications.status='passed'，回写 problems.is_verified / verified_by / verified_at
    - 未通过 → problem_verifications.status='failed'
    """
    verification = await db.get(ProblemVerification, verification_id)
    if verification is None:
        return
    problem = await db.get(Problem, verification.problem_id)
    if problem is None:
        return
    verification.status = "passed" if passed else "failed"
    if passed:
        problem.is_verified = True
        problem.verified_by = verifier_id
        problem.verified_at = datetime.now()
