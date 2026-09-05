"""标签管理业务逻辑（docs/contracts/problems.md problem_tags / 端点表）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TagStatus
from app.models.problem import ProblemTag
from app.repositories.problem import TagRepository
from app.schemas.problem import TagCreate, TagUpdate
from app.core.exceptions import APIError, RESOURCE_DUPLICATE, RESOURCE_NOT_FOUND, RESOURCE_STATE_CONFLICT


class TagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TagRepository(db)

    async def get(self, tag_id: uuid.UUID) -> ProblemTag:
        tag = await self.repo.get_by_id(tag_id)
        if tag is None:
            raise APIError(RESOURCE_NOT_FOUND, "标签不存在", 404)
        return tag

    async def list_active(self) -> list[ProblemTag]:
        """激活标签（公开：打标选择器与题库筛选用）。"""
        return await self.repo.list_active()

    async def list_page(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[ProblemTag], int]:
        """激活标签分页列表（支持 keyword 搜索）。"""
        return await self.repo.list_page(keyword, page, page_size)

    async def list_all_page(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[ProblemTag], int]:
        """管理分页列表：含已归档（激活在前），支持 keyword 模糊搜索。"""
        return await self.repo.list_all_page(keyword, page, page_size)

    async def create(self, body: TagCreate) -> ProblemTag:
        existing = await self.repo.get_by_name(body.name)
        if existing is not None:
            raise APIError(RESOURCE_DUPLICATE, "标签名已存在", 409)
        tag = ProblemTag(name=body.name, color=body.color, status=TagStatus.ACTIVE)
        return await self.repo.create(tag)

    async def update(self, tag_id: uuid.UUID, body: TagUpdate) -> ProblemTag:
        tag = await self.get(tag_id)
        if body.name is not None and body.name != tag.name:
            duplicate = await self.repo.get_by_name(body.name)
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
        if tag.status == TagStatus.ARCHIVED:
            raise APIError(RESOURCE_STATE_CONFLICT, "标签已归档", 409)
        tag.status = TagStatus.ARCHIVED
        tag.updated_at = datetime.now()
        await self.db.flush()
        return tag
