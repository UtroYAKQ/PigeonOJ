"""通用文件上传路由（统一前缀 /api/v1）。"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.api.deps import FileServiceDep
from app.models.user import User
from app.schemas.file import AvatarUploadResult, ImageUploadResult
from app.core.dependency import get_current_admin, get_current_user
from app.core.exceptions import APIError, RESOURCE_NOT_FOUND
from app.utils.response import ApiResponse, ok
from app.core.storage import S3Error, get_storage

router = APIRouter(prefix="/files", tags=["files"])

# 公开读取白名单：用户头像 / 公共图片、站点 Logo（判题测试点不在其列）
_PUBLIC_FILE_PREFIXES = ("users/", "site/logo/")
# 站内对象 key 含 uuid、内容不可变：可放心长缓存（浏览器无须重复回源拉大图）
_CACHE_CONTROL = "public, max-age=31536000, immutable"


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


@router.post("/upload/site-logo", response_model=ApiResponse[ImageUploadResult])
async def upload_site_logo(
    service: FileServiceDep,
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
) -> ApiResponse[ImageUploadResult]:
    """站点 Logo 上传（仅 admin）：用于站点配置 site.logo。"""
    return ok(await service.upload_site_logo(admin.id, file))


@router.get("/{object_key:path}")
async def read_file(object_key: str, request: Request):
    """读取用户头像等公开展示文件；判题测试点不使用此接口。

    对象 key 含 uuid 且内容不可变，返回长缓存头（immutable）+ ETag；
    命中 If-None-Match 时回 304，避免重复回源 MinIO 拉整图。
    """
    if not object_key.startswith(_PUBLIC_FILE_PREFIXES):
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404)
    try:
        content, content_type = await get_storage().get_bytes(object_key)
    except (OSError, S3Error) as exc:
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404) from exc
    etag = f'"{hashlib.sha256(object_key.encode()).hexdigest()[:16]}-{len(content):x}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL})
    # 内容已在内存（MinIO get_bytes），用 Response 而非 FileResponse：
    # starlette 1.0 的 FileResponse 仅接受 path（0.38~0.4x 的 content= 参数已移除），
    # Response 全版本兼容且语义正确
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": _CACHE_CONTROL, "ETag": etag},
    )
