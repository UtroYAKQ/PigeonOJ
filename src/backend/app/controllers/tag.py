"""标签管理业务逻辑（docs/contracts/problems.md problem_tags / 端点表）。

标签是 admin 维护的全局分类体系（替代 difficulty 枚举，
见 docs/decisions/2026-08-24-remove-difficulty-use-tags.md）：
- 归档不删除：题目既有关联保留展示，但不再可被新题目选择；
- 名称全局唯一，重复创建返回 RESOURCE_DUPLICATE（409 信封）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.problem import ProblemTag
from app.schemas.problem import TagCreate, TagUpdate
from app.core.exceptions import APIError, RESOURCE_DUPLICATE, RESOURCE_NOT_FOUND, RESOURCE_STATE_CONFLICT


class TagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, tag_id: uuid.UUID) -> ProblemTag:
        tag = await self.db.get(ProblemTag, tag_id)
        if tag is None:
            raise APIError(RESOURCE_NOT_FOUND, "标签不存在", 404)
        return tag

    async def list_active(self) -> list[ProblemTag]:
        """激活标签（公开：打标选择器与题库筛选用）。"""
        return list(
            (
                await self.db.execute(
                    select(ProblemTag)
                    .where(ProblemTag.status == "active")
                    .order_by(ProblemTag.name)
                )
            ).scalars()
        )

    async def list_all(self) -> list[ProblemTag]:
        """管理全量列表：激活在前，归档在后，组内按名称排序。"""
        return list(
            (
                await self.db.execute(
                    select(ProblemTag).order_by(ProblemTag.status, ProblemTag.name)
                )
            ).scalars()
        )

    async def create(self, body: TagCreate) -> ProblemTag:
        existing = await self.db.scalar(select(ProblemTag).where(ProblemTag.name == body.name))
        if existing is not None:
            raise APIError(RESOURCE_DUPLICATE, "标签名已存在", 409)
        tag = ProblemTag(name=body.name, color=body.color, status="active")
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def update(self, tag_id: uuid.UUID, body: TagUpdate) -> ProblemTag:
        tag = await self.get(tag_id)
        if body.name is not None and body.name != tag.name:
            duplicate = await self.db.scalar(
                select(ProblemTag).where(ProblemTag.name == body.name, ProblemTag.id != tag_id)
            )
            if duplicate is not None:
                raise APIError(RESOURCE_DUPLICATE, "标签名已存在", 409)
            tag.name = body.name
        if body.color is not None:
            tag.color = body.color
        tag.updated_at = datetime.now()
        await self.db.flush()
        return tag

    async def archive(self, tag_id: uuid.UUID) -> ProblemTag:
        tag = await self.get(tag_id)
        if tag.status == "archived":
            raise APIError(RESOURCE_STATE_CONFLICT, "标签已归档", 409)
        tag.status = "archived"
        tag.updated_at = datetime.now()
        await self.db.flush()
        return tag
