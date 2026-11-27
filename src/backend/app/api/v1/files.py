"""通用文件上传路由（统一前缀 /api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from app.api.deps import FileServiceDep, get_current_admin, get_current_user
from app.models.user import User
from app.schemas.file import AvatarUploadResult, ImageUploadResult
from app.core.exceptions import APIError, RESOURCE_NOT_FOUND
from app.utils.response import ApiResponse, ok
from app.core.storage import S3Error

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
async def read_file(
    object_key: str,
    request: Request,
    service: FileServiceDep,
    w: int | None = Query(None, ge=32, le=1920, description="缩略图宽度档位"),
):
    """读取用户头像等公开展示文件；判题测试点不使用此接口。

    对象 key 含 uuid 且内容不可变，返回长缓存头（immutable）+ ETag；
    命中 If-None-Match 时回 304，避免重复回源 MinIO 拉整图。
    `?w=` 命中固定档位（THUMB_WIDTHS）时返回 WebP 缩略图：首次生成后写入对象存储，
    后续请求直接命中缩略图；GIF 与无法转码的图片回退原图。
    """
    if not object_key.startswith(_PUBLIC_FILE_PREFIXES):
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404)
    try:
        content, content_type, etag = await service.read_public_file(object_key, w)
    except (OSError, S3Error) as exc:
        raise APIError(RESOURCE_NOT_FOUND, "文件不存在", 404) from exc
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL})
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": _CACHE_CONTROL, "ETag": etag},
    )
