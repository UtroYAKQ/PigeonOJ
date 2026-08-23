"""MinIO 对象存储（兼容层，已迁移至 shared/infra/storage.py）。

保留此文件以兼容旧有导入：
    from app.shared.storage import get_storage, S3Error, MinioStorage

新代码请直接使用：
    from app.shared.infra.storage import get_storage, S3Error, MinioStorage
"""
from app.shared.infra.storage import MinioStorage, S3Error, StoredObject, get_storage  # noqa: F401

__all__ = ["MinioStorage", "S3Error", "StoredObject", "get_storage"]
