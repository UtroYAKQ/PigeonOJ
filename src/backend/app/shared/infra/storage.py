"""通用 MinIO 对象存储工具。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from app.config import get_settings

try:
    from minio.error import S3Error
except ModuleNotFoundError:  # 测试/最小 API 环境不要求安装 MinIO SDK
    S3Error = OSError


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    content_type: str
    size: int


class MinioStorage:
    """仅由服务端使用的 MinIO 适配器；不签发测试点公开 URL。"""

    def __init__(self) -> None:
        try:
            from minio import Minio
        except ModuleNotFoundError as exc:
            raise OSError("MinIO SDK is not installed") from exc
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client: Any = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def put_bytes(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        await asyncio.to_thread(self._put_bytes, object_key, content, content_type)
        return StoredObject(object_key, content_type, len(content))

    def _put_bytes(self, object_key: str, content: bytes, content_type: str) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self.client.put_object(self.bucket, object_key, BytesIO(content), len(content), content_type=content_type)

    async def get_bytes(self, object_key: str) -> tuple[bytes, str]:
        return await asyncio.to_thread(self._get_bytes, object_key)

    def _get_bytes(self, object_key: str) -> tuple[bytes, str]:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read(), response.headers.get("Content-Type", "application/octet-stream")
        finally:
            response.close()
            response.release_conn()

    async def delete(self, object_key: str) -> None:
        await asyncio.to_thread(self.client.remove_object, self.bucket, object_key)


_storage: MinioStorage | None = None


def get_storage() -> MinioStorage:
    global _storage
    if _storage is None:
        _storage = MinioStorage()
    return _storage


__all__ = ["MinioStorage", "S3Error", "StoredObject", "get_storage"]
