"""HTTP 中间件：全量请求日志（request_logs）与未处理异常日志（exception_logs）。

实现为纯 ASGI 中间件（非 BaseHTTPMiddleware）：await call_next(request) 等
应用整链返回后才落库——此时路由依赖 teardown 已完成、业务事务已 commit。
此前经 BaseHTTPMiddleware 的 finally 写日志，与未提交的路由事务形成锁等待
（request_logs.user_id FK 需要 users 行的 KEY SHARE 锁，被事务持有），
响应又被阻塞的中间件卡住 → 互相等待，请求永久挂起（Windows proactor 集成
测试中表现为用例随机挂死）。纯 ASGI 写法在 await app(...) 返回后再写库，
锁竞争窗口自然消除。
"""
from __future__ import annotations

import logging
import time
import traceback
import uuid
import typing

from fastapi import Request

from app.enums import LogLevel
from app.repositories.audit import write_exception_log, write_request_log
from app.core.database import SessionLocal
from app.core.dependency import REQUEST_STATE_USER_ID
from app.services.system_config import ConfigService
from app.utils.request_meta import resolve_client_ip

logger = logging.getLogger(__name__)

# GET 日志降噪开关的缓存（秒）：避免每个请求都查一次 system_configs
_RECORD_GET_CACHE_TTL = 10
_record_get_cache: list = [True, 0.0]  # [开关值, 过期时间戳]


async def _should_record_get() -> bool:
    """读取 log.record_get_logs 开关（10 秒进程内缓存，读多写少的配置项）。"""
    import time as _time

    now = _time.perf_counter()
    if now < _record_get_cache[1]:
        return bool(_record_get_cache[0])
    try:
        async with SessionLocal() as db:
            value = await ConfigService(db).should_record_get_logs()
        _record_get_cache[0] = value
        _record_get_cache[1] = now + _RECORD_GET_CACHE_TTL
        return value
    except Exception:  # noqa: BLE001 - 配置读取失败按默认记录处理
        logger.exception("record_get_logs 配置读取失败")
        _record_get_cache[1] = now + _RECORD_GET_CACHE_TTL
        return True


class RequestLoggingMiddleware:
    """请求级审计：request_id 追踪 + 落库（写入失败不影响主流程，docs/contracts/admin.md）。

    纯 ASGI：应用整链（含异常处理器与依赖 teardown / 事务提交）返回后再写
    request_logs / exception_logs；response.start 捕获状态码并回填 request_id 头。
    """

    def __init__(self, app: typing.Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status_code = 500
        captured_exception: BaseException | None = None

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:  # noqa: BLE001 - 需记录全部未处理异常
            captured_exception = exc
            try:
                async with SessionLocal() as db:
                    await write_exception_log(
                        db,
                        level=LogLevel.ERROR,
                        message=str(exc)[:2000],
                        traceback=traceback.format_exc()[:8000],
                        request_id=request_id,
                        user_id=None,
                    )
            except Exception:  # noqa: BLE001 - 日志写入失败不影响主流程
                logger.exception("exception_log 写入失败")
            raise
        finally:
            try:
                duration_ms = int((time.perf_counter() - start) * 1000)
                path = scope.get("path", "")
                if len(path) > 512:
                    path = path[:512]
                # 认证依赖（_load_user）成功时写入 request.state；匿名请求无此属性 → None
                state = scope.get("state") or {}
                log_user_id = state.get(REQUEST_STATE_USER_ID)
                # GET 日志可由 log.record_get_logs 降噪关闭；写操作始终记录（审计需要）
                if not (scope.get("method") == "GET" and not await _should_record_get()):
                    # Request(scope) 为轻量包装（不消费 receive），供请求头 / client 元信息解析
                    async with SessionLocal() as db:
                        await write_request_log(
                            db,
                            request_id=request_id,
                            method=scope.get("method", ""),
                            path=path,
                            status_code=status_code,
                            user_id=log_user_id,
                            ip_address=resolve_client_ip(Request(scope)),
                            user_agent=_header_of(scope, "user-agent"),
                            duration_ms=duration_ms,
                        )
            except Exception:  # noqa: BLE001 - 日志写入失败不影响主流程
                logger.exception("request_log 写入失败")


def _header_of(scope, name: str) -> str | None:
    """从 ASGI scope.headers 取请求头（bytes 列表）。"""
    for key, value in scope.get("headers") or []:
        if key.decode("latin-1").lower() == name:
            return value.decode("latin-1")
    return None


def make_middlewares() -> list:
    """应用中间件列表（按注册顺序生效）。"""
    return [RequestLoggingMiddleware]
