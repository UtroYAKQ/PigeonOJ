"""Redis 客户端（兼容层，已迁移至 shared/infra/redis.py）。

保留此文件以兼容旧有导入：
    from app.shared.redis import get_redis, redis_get, redis_set, ...

新代码请直接使用：
    from app.shared.infra.redis import get_redis, redis_get, redis_set, ...
"""
from app.shared.infra.redis import (  # noqa: F401
    close_redis,
    get_redis,
    redis_delete,
    redis_get,
    redis_get_json,
    redis_incr,
    redis_set,
    redis_set_json,
)

__all__ = [
    "get_redis",
    "close_redis",
    "redis_get",
    "redis_set",
    "redis_delete",
    "redis_get_json",
    "redis_set_json",
    "redis_incr",
]
