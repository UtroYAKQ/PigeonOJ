"""文件模块 Service：校验并写入 MinIO。"""
from __future__ import annotations

import uuid
from typing import TypeVar

from fastapi import UploadFile

from app.core.exceptions import APIError, PARAM_FORMAT_INVALID, RATE_LIMITED, SYSTEM_UPSTREAM_FAILURE
from app.core.redis import redis_incr
from app.core.storage import S3Error, get_storage
from app.schemas.file import AvatarUploadResult, ImageUploadResult

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_BYTES = 5 * 1024 * 1024

# 上传频控（docs/security.md「上传与文件安全」）：按用户 Redis 固定窗口计数，
# 防止循环上传垃圾对象耗尽对象存储；仅通过类型/大小校验、即将写入存储的请求消耗配额
_UPLOAD_QUOTAS = {
    "avatar": (10, 3600),   # (窗口内次数上限, 窗口秒数)
    "image": (30, 3600),
    "site_logo": (10, 3600),
}

R = TypeVar("R", AvatarUploadResult, ImageUploadResult)


async def _ensure_upload_quota(user_id: uuid.UUID, kind: str) -> None:
    limit, window = _UPLOAD_QUOTAS[kind]
    count = await redis_incr(f"upload:rate:{kind}:{user_id}", ttl_seconds=window)
    if count > limit:
        raise APIError(RATE_LIMITED, "上传过于频繁，请稍后再试", 429)


class FileService:
    async def upload_avatar(self, user_id: uuid.UUID, file: UploadFile) -> AvatarUploadResult:
        content_type, content = await _validate_image(
            file,
            max_bytes=_MAX_AVATAR_BYTES,
            type_error="头像仅支持 JPG、PNG、WEBP 或 GIF",
            size_error="头像大小不能超过 2MB",
            empty_error="头像文件不能为空",
        )
        await _ensure_upload_quota(user_id, "avatar")

        object_key = f"users/{user_id}/avatar/{uuid.uuid4().hex}"
        return await _store_image(object_key, content_type, content, AvatarUploadResult)

    async def upload_image(self, user_id: uuid.UUID, file: UploadFile) -> ImageUploadResult:
        """公共图片上传：登录用户可用，供题面插图等 Markdown 场景引用。"""
        content_type, content = await _validate_image(
            file,
            max_bytes=_MAX_IMAGE_BYTES,
            type_error="图片仅支持 JPG、PNG、WEBP 或 GIF",
            size_error="图片大小不能超过 5MB",
            empty_error="图片文件不能为空",
        )
        await _ensure_upload_quota(user_id, "image")

        object_key = f"users/{user_id}/images/{uuid.uuid4().hex}"
        return await _store_image(object_key, content_type, content, ImageUploadResult)

    async def upload_site_logo(self, user_id: uuid.UUID, file: UploadFile) -> ImageUploadResult:
        """站点 Logo 上传：仅 admin，供站点配置 site.logo 引用。"""
        content_type, content = await _validate_image(
            file,
            max_bytes=_MAX_IMAGE_BYTES,
            type_error="站点 Logo 仅支持 JPG、PNG、WEBP 或 GIF",
            size_error="站点 Logo 大小不能超过 5MB",
            empty_error="站点 Logo 文件不能为空",
        )
        await _ensure_upload_quota(user_id, "site_logo")

        object_key = f"site/logo/{uuid.uuid4().hex}"
        return await _store_image(object_key, content_type, content, ImageUploadResult)


async def _validate_image(
    file: UploadFile,
    *,
    max_bytes: int,
    type_error: str,
    size_error: str,
    empty_error: str,
) -> tuple[str, bytes]:
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise APIError(PARAM_FORMAT_INVALID, type_error, 400)
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise APIError(PARAM_FORMAT_INVALID, size_error, 400)
    if not content:
        raise APIError(PARAM_FORMAT_INVALID, empty_error, 400)
    return content_type, content


async def _store_image(object_key: str, content_type: str, content: bytes, result_cls: type[R]) -> R:
    try:
        stored = await get_storage().put_bytes(object_key, content, content_type)
    except (OSError, S3Error) as exc:
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "文件存储失败，请稍后重试", 503) from exc
    return result_cls(
        url=f"/api/v1/files/{stored.object_key}",
        content_type=stored.content_type,
        size=stored.size,
    )
