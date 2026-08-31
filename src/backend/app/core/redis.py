"""Redis 客户端与短生命周期数据读写。

Key 约定见 docs/operations.md「Redis 约定」：
- `email:code:<email>:<purpose>`  邮箱验证码 + 错误计数（不落库）
- `email:resend:<email>:<purpose>` 验证码重发间隔
- `session:<token_hash>`          会话热点缓存（token 哈希为 key，见 shared/security.py）
- `login:fail:<email>`            登录失败计数（超次触发临时锁定）
- `login:lock:<email>`            登录临时锁定标记（TTL 到期自动恢复，不改动账号状态）
- `sandbox:node:<id>`             沙箱节点运行时状态

客户端按事件循环隔离：API 进程单循环、Judge Worker 每个任务 asyncio.run 独立循环、
心跳线程另有循环；aioredis 连接绑定创建时的循环，跨循环复用会报
「attached to a different loop」，因此循环切换时必须重建客户端。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis

from app.settings.config import get_settings

_client: aioredis.Redis | None = None
_client_loop_id: int | None = None

# Key 前缀约定（docs/operations.md「Redis 约定」）
SANDBOX_NODE_KEY_PREFIX = "sandbox:node:"
SESSION_KEY_PREFIX = "session:"
EMAIL_CODE_KEY_PREFIX = "email:code:"
EMAIL_RESEND_KEY_PREFIX = "email:resend:"


def get_redis() -> aioredis.Redis:
    """获取当前事件循环的 Redis 客户端（懒初始化，循环内单例）。"""
    global _client, _client_loop_id
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = None  # 无运行中循环（如模块导入期）；仍返回缓存实例
    if _client is None or (loop_id is not None and _client_loop_id != loop_id):
        _client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        _client_loop_id = loop_id
    return _client


async def close_redis() -> None:
    """关闭 Redis 客户端（测试 / 应用退出时调用）。"""
    global _client, _client_loop_id
    if _client is not None:
        await _client.aclose()
        _client = None
        _client_loop_id = None


async def redis_get(key: str) -> str | None:
    return await get_redis().get(key)


async def redis_set(key: str, value: str, ttl_seconds: int | None = None) -> None:
    if ttl_seconds is not None:
        await get_redis().set(key, value, ex=ttl_seconds)
    else:
        await get_redis().set(key, value)


async def redis_delete(key: str) -> None:
    await get_redis().delete(key)


async def redis_get_json(key: str) -> Any | None:
    raw = await redis_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def redis_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    await redis_set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)


async def redis_incr(key: str, ttl_seconds: int | None = None) -> int:
    """自增计数；首次创建时若给定 TTL 则设置过期时间（用于登录失败窗口等）。"""
    r = get_redis()
    val = await r.incr(key)
    if val == 1 and ttl_seconds is not None:
        await r.expire(key, ttl_seconds)
    return val
