"""文件模块 Service：校验、转码、缩略图与写入 MinIO。"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from io import BytesIO
from typing import TypeVar

from fastapi import UploadFile
from PIL import Image

# 上传侧像素上限：5MB 扁平 PNG 可伪造数亿像素（解码即数百 MB~GB 内存），
# 放宽默认炸弹阈值到 1.2 亿像素（用户当前 9500 万像素横幅可通过），超过直接拒绝
Image.MAX_IMAGE_PIXELS = 120_000_000

from app.core.exceptions import APIError, PARAM_FORMAT_INVALID, RATE_LIMITED, SYSTEM_UPSTREAM_FAILURE
from app.core.redis import UPLOAD_RATE_KEY_PREFIX, redis_incr
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

_GIF_TYPE = "image/gif"
_WEBP_TYPE = "image/webp"
# 统一转 WebP：非 GIF 图片上传即重编码（PNG 原图在手机上动辄数百 KB~数 MB），
# 质量 82 时体积通常降 50%~80%；转码后反而更大的小图保留原图。
_WEBP_QUALITY = 82
# 缩略图只接受固定宽度档位：前端按展示尺寸就近取档，任意 w 会生成无限派生对象
THUMB_WIDTHS = (96, 192, 384, 640, 960, 1280)


def thumb_object_key(object_key: str, width: int) -> str:
    """缩略图派生对象 key（与原图同前缀，仍在公开读取白名单内）。"""
    return f"{object_key}@w{width}.webp"


def _etag(key: str, size: int) -> str:
    return f'"{hashlib.sha256(key.encode()).hexdigest()[:16]}-{size:x}"'

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
    count = await redis_incr(f"{UPLOAD_RATE_KEY_PREFIX}{kind}:{user_id}", ttl_seconds=window)
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

    async def read_public_file(self, object_key: str, width: int | None) -> tuple[bytes, str, str]:
        """读取公开文件；width 命中固定档位时返回缩略图（实现见 _read_public_file）。"""
        if width is not None and width not in THUMB_WIDTHS:
            raise APIError(PARAM_FORMAT_INVALID, "不支持的缩略图宽度", 400)
        return await _read_public_file(object_key, width)


async def _validate_image(
    file: UploadFile,
    *,
    max_bytes: int,
    max_width: int = _MAX_IMAGE_WIDTH,
    type_error: str,
    size_error: str,
    empty_error: str,
) -> tuple[str, bytes]:
    """读取并校验图片；非 GIF 图转 WebP（宽度超过 max_width 时先等比缩宽）。"""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise APIError(PARAM_FORMAT_INVALID, type_error, 400)
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise APIError(PARAM_FORMAT_INVALID, size_error, 400)
    if not content:
        raise APIError(PARAM_FORMAT_INVALID, empty_error, 400)
    if content_type == _GIF_TYPE or max_width <= 0:
        return content_type, content
    try:
        encoded, converted = await asyncio.to_thread(_encode_webp, content, max_width)
    except Exception as exc:
        # 像素炸弹（Image.MAX_IMAGE_PIXELS）/ 解码失败 / 格式伪装
        raise APIError(PARAM_FORMAT_INVALID, "图片尺寸或内容无效", 400) from exc
    return (_WEBP_TYPE if converted else content_type), encoded


def _encode_webp(content: bytes, max_width: int) -> tuple[bytes, bool]:
    """PNG/JPEG/WEBP 重编码为 WebP，返回 (内容, 是否已转码)。

    动图（多帧）保留原格式；编码失败或转码后体积不降时回退原图。
    """
    with Image.open(BytesIO(content)) as img:
        img.load()
        if getattr(img, "is_animated", False):
            return content, False
        resized = False
        if max_width > 0 and img.width > max_width:
            height = max(1, round(img.height * max_width / img.width))
            img = img.resize((max_width, height), Image.LANCZOS)
            resized = True
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        target = img.convert("RGBA" if has_alpha else "RGB")
    try:
        buf = BytesIO()
        target.save(buf, format="WEBP", quality=_WEBP_QUALITY, method=4)
    except Exception:
        return content, False
    encoded = buf.getvalue()
    if not resized and len(encoded) >= len(content):
        return content, False
    return encoded, True


async def _read_public_file(object_key: str, width: int | None) -> tuple[bytes, str, str]:
    """读取公开文件；width 命中白名单时返回 WebP 缩略图（首次生成后写回存储）。

    返回 (内容, content-type, ETag)。缩略图对象与原图同前缀、内容不可变，
    因此同样适用长缓存 + 304；GIF 与无法转码的图片直接回退原图。
    """
    if width is not None:
        thumb_key = thumb_object_key(object_key, width)
        try:
            thumb, thumb_type = await get_storage().get_bytes(thumb_key)
        except (OSError, S3Error):
            pass
        else:
            return thumb, thumb_type, _etag(thumb_key, len(thumb))
    content, content_type = await get_storage().get_bytes(object_key)
    etag = _etag(object_key, len(content))
    if width is None or content_type == _GIF_TYPE:
        return content, content_type, etag
    try:
        encoded, converted = await asyncio.to_thread(_encode_webp, content, width)
    except Exception:
        return content, content_type, etag
    if not converted:
        return content, content_type, etag
    thumb_key = thumb_object_key(object_key, width)
    try:
        await get_storage().put_bytes(thumb_key, encoded, _WEBP_TYPE)
    except (OSError, S3Error):
        pass
    return encoded, _WEBP_TYPE, _etag(thumb_key, len(encoded))


async def _store_image(object_key: str, content_type: str, content: bytes, result_cls: type[R]) -> R:
    try:
        stored = await get_storage().put_bytes(object_key, content, content_type)
    except (OSError, S3Error) as exc:
        raise APIError(SYSTEM_UPSTREAM_FAILURE, "文件存储失败，请稍后重试", 502) from exc
    return result_cls(
        url=f"/api/v1/files/{stored.object_key}",
        content_type=stored.content_type,
        size=stored.size,
    )
