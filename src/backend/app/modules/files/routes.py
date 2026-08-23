"""通用文件上传路由（统一前缀 /api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.service import FileService
from app.modules.users.models import User
from app.shared.infra.database import get_db
from app.modules.users.deps import get_current_user
from app.shared.common.errors import APIError, AUTH_FORBIDDEN, RESOURCE_NOT_FOUND
from app.shared.auth.permissions import MANAGER_ROLE_CODES, get_user_role_codes
from app.shared.common.response import ok
from app.shared.infra.storage import S3Error, get_storage

router = APIRouter(prefix="/files", tags=["files"])


async def _require_problem_manager(user: User, db: AsyncSession) -> None:
    codes = await get_user_role_codes(db, user.id)
    if not MANAGER_ROLE_CODES.intersection(codes):
        raise APIError(AUTH_FORBIDDEN, "无权限上传该类型文件", 403)


@router.post("/upload/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    result = await FileService().upload_avatar(current_user.id, file)
    return ok(result)


@router.post("/upload/spj")
async def upload_spj(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SPJ checker 源码上传：仅题目管理角色（docs/contracts/problems.md 端点表）。"""
    await _require_problem_manager(current_user, db)
    return ok(await FileService().upload_spj(current_user.id, file))


@router.get("/{object_key:path}")
async def read_file(object_key: str):
    """读取用户头像等公开展示文件；判题测试点不使用此接口。"""
    if not object_key.startswith("users/"):
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404)
    try:
        content, content_type = await get_storage().get_bytes(object_key)
    except (OSError, S3Error) as exc:
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404) from exc
    return Response(content=content, media_type=content_type)
