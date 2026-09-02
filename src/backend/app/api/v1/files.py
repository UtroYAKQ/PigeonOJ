"""通用文件上传路由（统一前缀 /api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.api.deps import FileServiceDep
from app.models.user import User
from app.schemas.file import AvatarUploadResult, ImageUploadResult
from app.core.dependency import get_current_user
from app.core.exceptions import APIError, RESOURCE_NOT_FOUND
from app.utils.response import ApiResponse, ok
from app.core.storage import S3Error, get_storage

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload/avatar", response_model=ApiResponse[AvatarUploadResult])
async def upload_avatar(
    service: FileServiceDep,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AvatarUploadResult]:
    return ok(await service.upload_avatar(current_user.id, file))


@router.post("/upload/image", response_model=ApiResponse[ImageUploadResult])
async def upload_image(
    service: FileServiceDep,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ImageUploadResult]:
    """公共图片上传（登录用户可用）：题面插图等 Markdown 引用场景。"""
    return ok(await service.upload_image(current_user.id, file))


@router.get("/{object_key:path}")
async def read_file(object_key: str):
    """读取用户头像等公开展示文件；判题测试点不使用此接口。"""
    if not object_key.startswith("users/"):
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404)
    try:
        content, content_type = await get_storage().get_bytes(object_key)
    except (OSError, S3Error) as exc:
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404) from exc
    # 内容已在内存（MinIO get_bytes），用 Response 而非 FileResponse：
    # starlette 1.0 的 FileResponse 仅接受 path（0.38~0.4x 的 content= 参数已移除），
    # Response 全版本兼容且语义正确
    return Response(content=content, media_type=content_type)
