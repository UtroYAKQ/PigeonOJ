"""文件模块 Service：校验并写入 MinIO。"""
from __future__ import annotations

import uuid

from fastapi import UploadFile

from app.shared.errors import APIError, PARAM_FORMAT_INVALID, SYSTEM_UPSTREAM_FAILURE
from app.shared.storage import S3Error, get_storage

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_MAX_SPJ_BYTES = 16 * 1024 * 1024


class FileService:
    async def upload_avatar(self, user_id: uuid.UUID, file: UploadFile) -> dict:
        content_type = (file.content_type or "").lower()
        if content_type not in _ALLOWED_IMAGE_TYPES:
            raise APIError(PARAM_FORMAT_INVALID, "头像仅支持 JPG、PNG、WEBP 或 GIF", 400)
        content = await file.read(_MAX_AVATAR_BYTES + 1)
        if len(content) > _MAX_AVATAR_BYTES:
            raise APIError(PARAM_FORMAT_INVALID, "头像大小不能超过 2MB", 400)
        if not content:
            raise APIError(PARAM_FORMAT_INVALID, "头像文件不能为空", 400)

        object_key = f"users/{user_id}/avatar/{uuid.uuid4().hex}"
        try:
            stored = await get_storage().put_bytes(object_key, content, content_type)
        except (OSError, S3Error) as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "文件存储失败，请稍后重试", 503) from exc
        return {
            "oss_id": stored.object_key,
            "url": f"/api/v1/files/{stored.object_key}",
            "content_type": stored.content_type,
            "size": stored.size,
        }

    async def upload_spj(self, user_id: uuid.UUID, file: UploadFile) -> dict:
        """SPJ checker 源码上传（docs/contracts/problems.md：≤16MB，返回 ossId）。"""
        del user_id  # 预留：对象路径按题目归属组织时使用
        content = await file.read(_MAX_SPJ_BYTES + 1)
        if len(content) > _MAX_SPJ_BYTES:
            raise APIError(PARAM_FORMAT_INVALID, "SPJ 文件大小不能超过 16MB", 400)
        if not content:
            raise APIError(PARAM_FORMAT_INVALID, "SPJ 文件不能为空", 400)
        content_type = "text/x-c++src"
        if not (file.filename or "").lower().endswith((".cpp", ".cc", ".cxx")):
            raise APIError(PARAM_FORMAT_INVALID, "SPJ 仅支持 C++ 源码文件（.cpp）", 400)

        object_key = f"problems/spj/{uuid.uuid4().hex}.cpp"
        try:
            stored = await get_storage().put_bytes(object_key, content, "text/x-c++src")
        except (OSError, S3Error) as exc:
            raise APIError(SYSTEM_UPSTREAM_FAILURE, "文件存储失败，请稍后重试", 503) from exc
        return {
            "oss_id": stored.object_key,
            "content_type": stored.content_type,
            "size": stored.size,
        }
