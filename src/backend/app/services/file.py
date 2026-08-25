"""文件模块 Service：校验并写入 MinIO。"""
from __future__ import annotations

import uuid

from fastapi import UploadFile

from app.core.exceptions import APIError, PARAM_FORMAT_INVALID, SYSTEM_UPSTREAM_FAILURE
from app.core.storage import S3Error, get_storage
from app.schemas.file import AvatarUploadResult, ImageUploadResult

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class FileService:
    async def upload_avatar(self, user_id: uuid.UUID, file: UploadFile) -> AvatarUploadResult:
        content_type, content = await _validate_image(
            file,
            max_bytes=_MAX_AVATAR_BYTES,
            type_error="头像仅支持 JPG、PNG、WEBP 或 GIF",
            size_error="头像大小不能超过 2MB",
            empty_error="头像文件不能为空",
        )

        object_key = f"users/{user_id}/avatar/{uuid.uuid4().hex}"
        return await _store_image(object_key, content_type, content)

    async def upload_image(self, user_id: uuid.UUID, file: UploadFile) -> ImageUploadResult:
        """公共图片上传：登录用户可用，供题面插图等 Markdown 场景引用。"""
        content_type, content = await _validate_image(
            file,
            max_bytes=_MAX_IMAGE_BYTES,
            type_error="图片仅支持 JPG、PNG、WEBP 或 GIF",
            size_error="图片大小不能超过 5MB",
            empty_error="图片文件不能为空",
        )

        object_key = f"users/{user_id}/images/{uuid.uuid4().hex}"
        return await _store_image(object_key, content_type, content)


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


async def _store_image(object_key: str, content_type: str, content: bytes) -> ImageUploadResult:
    try:
        stored = await get_storage().put_bytes(object_key, content, content_type)
    except (OSError, S3Error) as exc:
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "文件存储失败，请稍后重试", 503) from exc
    return ImageUploadResult(
        oss_id=stored.object_key,
        url=f"/api/v1/files/{stored.object_key}",
        content_type=stored.content_type,
        size=stored.size,
    )
