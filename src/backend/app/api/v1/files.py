"""通用文件上传路由（统一前缀 /api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.services.file import FileService
from app.models.user import User
from app.core.dependency import get_current_user
from app.core.exceptions import APIError, RESOURCE_NOT_FOUND
from app.utils.response import ok
from app.core.storage import S3Error, get_storage

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    result = await FileService().upload_avatar(current_user.id, file)
    return ok(result)


@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """公共图片上传（登录用户可用）：题面插图等 Markdown 引用场景。"""
    result = await FileService().upload_image(current_user.id, file)
    return ok(result)


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
