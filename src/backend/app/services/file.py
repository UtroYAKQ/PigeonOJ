"""文件模块 Service：校验、降采样并写入 MinIO。"""
from __future__ import annotations

import asyncio
import uuid
from io import BytesIO
from typing import TypeVar

from fastapi import UploadFile
from PIL import Image

# 上传侧像素上限：5MB 扁平 PNG 可伪造数亿像素（解码即数百 MB~GB 内存），
# 放宽默认炸弹阈值到 1.2 亿像素（用户当前 9500 万像素横幅可通过），超过直接拒绝
Image.MAX_IMAGE_PIXELS = 120_000_000

from app.core.exceptions import APIError, PARAM_FORMAT_INVALID, RATE_LIMITED, SYSTEM_UPSTREAM_FAILURE
from app.core.redis import redis_incr
from app.core.storage import S3Error, get_storage
from app.schemas.file import AvatarUploadResult, ImageUploadResult

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_BYTES = 5 * 1024 * 1024

# 超大图整图解码是前端卡顿主因（一张 15000x6340 PNG 解码约 380MB 位图，
# 超出 Chromium 解码缓存即「显示后反复重解码」永久掉帧）：上传时统一降采样。
# GIF 不缩帧（动图逐帧重采样开销大且语义易破坏），PNG/JPEG/WEBP 等比缩宽。
_MAX_IMAGE_WIDTH = 1920
_MAX_AVATAR_WIDTH = 512

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
            max_width=_MAX_AVATAR_WIDTH,
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
            max_width=_MAX_AVATAR_WIDTH,
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
    max_width: int = _MAX_IMAGE_WIDTH,
    type_error: str,
    size_error: str,
    empty_error: str,
) -> tuple[str, bytes]:
    """读取并校验图片；超宽的非 GIF 图等比降采样到 max_width（原地重编码）。"""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise APIError(PARAM_FORMAT_INVALID, type_error, 400)
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise APIError(PARAM_FORMAT_INVALID, size_error, 400)
    if not content:
        raise APIError(PARAM_FORMAT_INVALID, empty_error, 400)
    if content_type != "image/gif" and max_width > 0:
        try:
            # 像素炸弹校验在 open()（仅解析头）即触发，超过 MAX_IMAGE_PIXELS 两倍直接拒绝
            with Image.open(BytesIO(content)):
                pass
        except Exception as exc:
            raise APIError(PARAM_FORMAT_INVALID, "图片尺寸或内容无效", 400) from exc
        content = await _downsample(content, content_type, max_width)
    return content_type, content


async def _downsample(content: bytes, content_type: str, max_width: int) -> bytes:
    """宽度超过 max_width 时等比缩宽并按原格式重编码；异常时回退原图。"""

    def _resize() -> bytes | None:
        try:
            with Image.open(BytesIO(content)) as img:
                if img.width <= max_width:
                    return None
                height = max(1, round(img.height * max_width / img.width))
                resized = img.resize((max_width, height), Image.LANCZOS)
                save_kwargs: dict = {}
                if content_type == "image/jpeg":
                    resized = resized.convert("RGB")
                    save_kwargs["quality"] = 88
                buf = BytesIO()
                resized.save(buf, format=_PIL_FORMATS[content_type], **save_kwargs)
                return buf.getvalue()
        except Exception:
            # 图片损坏 / 格式伪装等：回退原图，由展示端兜底
            return None

    resized = await asyncio.to_thread(_resize)
    return resized if resized is not None else content


_PIL_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


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
