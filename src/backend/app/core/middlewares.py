"""HTTP 中间件：全量请求日志（request_logs）与未处理异常日志（exception_logs）。

实现为纯 ASGI 中间件（非 BaseHTTPMiddleware）：await call_next(request) 等
应用整链返回后才 enqueue 日志——此时路由依赖 teardown 已完成、业务事务已 commit。
此前经 BaseHTTPMiddleware 的 finally 写日志，与未提交的路由事务形成锁等待
（request_logs.user_id FK 需要 users 行的 KEY SHARE 锁，被事务持有），
响应又被阻塞的中间件卡住 → 互相等待，请求永久挂起（Windows proactor 集成
测试中表现为用例随机挂死）。

日志不再逐请求开会话提交：响应返回后只入有界内存队列，由进程内单写协程
按 100 条或 200ms 批量 add_all + 一次 commit；队列满时 GET 可丢弃，写操作
与异常日志兜底直写。生命周期 shutdown 时 drain（见 core/init_app.py）。
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
import traceback
import uuid
import typing

from fastapi import Request

from app.enums import LogLevel
from app.repositories.audit import (
    ExceptionLogRecord,
    RequestLogRecord,
    add_exception_logs,
    add_request_logs,
    write_exception_log,
    write_request_log,
)
from app.core.database import SessionLocal
from app.core.dependency import REQUEST_STATE_USER_ID
from app.services.system_config import ConfigService
from app.utils.request_meta import parse_user_agent, resolve_client_ip

logger = logging.getLogger(__name__)

# GET 日志降噪开关的缓存（秒）：避免每个请求都查一次 system_configs
_RECORD_GET_CACHE_TTL = 10
_record_get_cache: list = [True, 0.0]  # [开关值, 过期时间戳]

# 批量写入参数（进程内单写协程；有界队列防止突发流量无限堆积）
_LOG_BATCH_SIZE = 100
_LOG_FLUSH_INTERVAL = 0.2
_LOG_QUEUE_MAXSIZE = 2048
_WRITE_WAIT_TIMEOUT = 5.0


class AuditLogWriter:
    """有界队列 + 单写协程：每批 100 条或 200ms 一次 commit。

    队列用标准库 `queue.Queue`（不绑定事件循环），写协程在 lifespan 所在的
    事件循环创建；每批用新 SessionLocal，绝不跨事件循环复用 AsyncSession。
    """

    def __init__(
        self,
        *,
        maxsize: int = _LOG_QUEUE_MAXSIZE,
        batch_size: int = _LOG_BATCH_SIZE,
        flush_interval: float = _LOG_FLUSH_INTERVAL,
    ) -> None:
        self._queue: queue.Queue[RequestLogRecord | ExceptionLogRecord] = queue.Queue(maxsize=maxsize)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wakeup: asyncio.Event | None = None
        self._closing = False
        self._pending_writes = 0
        self._idle = threading.Event()
        self._idle.set()
        self._idle_lock = threading.Lock()

    @property
    def queued(self) -> int:
        """当前待写队列长度（测试 / 观测用）。"""
        return self._queue.qsize()

    async def start(self) -> None:
        """在当前事件循环启动唯一写协程（lifespan startup 调用，幂等）。"""
        loop = asyncio.get_running_loop()
        if self._task is not None and not self._task.done() and self._loop is loop:
            return
        if self._task is not None and not self._task.done():
            # 非常规场景：旧循环仍有 worker，不能跨 loop 等待，取消即可
            self._task.cancel()
        self._loop = loop
        self._wakeup = asyncio.Event()
        self._closing = False
        self._task = asyncio.create_task(self._run(), name="audit-log-writer")

    def _notify(self) -> None:
        """唤醒写协程；跨线程时经 call_soon_threadsafe 设置事件。"""
        wakeup, loop = self._wakeup, self._loop
        if wakeup is None or loop is None:
            return
        try:
            if asyncio.get_running_loop() is loop:
                wakeup.set()
            elif loop.is_running():
                loop.call_soon_threadsafe(wakeup.set)
        except RuntimeError:  # 事件循环已关闭：flush() 仍可在当前循环兜底 drain
            pass

    async def enqueue(
        self, record: RequestLogRecord | ExceptionLogRecord, *, required: bool
    ) -> None:
        """入队轻量日志；队列满时 GET 可丢弃，写操作 / 异常日志兜底直写。"""
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            if required:
                await self._write_direct(record)
            else:
                logger.warning("请求日志队列已满，丢弃 GET 日志")
            return
        self._notify()

    def _take_batch(self) -> list[RequestLogRecord | ExceptionLogRecord]:
        batch: list[RequestLogRecord | ExceptionLogRecord] = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _begin_write(self) -> None:
        with self._idle_lock:
            self._pending_writes += 1
            self._idle.clear()

    def _end_write(self) -> None:
        with self._idle_lock:
            self._pending_writes -= 1
            if self._pending_writes == 0:
                self._idle.set()

    async def _write_batch(self, batch: list[RequestLogRecord | ExceptionLogRecord]) -> None:
        """一批日志共用一个会话，add_all 后一次 commit；失败只记日志不影响请求。"""
        requests = [r for r in batch if isinstance(r, RequestLogRecord)]
        exceptions = [r for r in batch if isinstance(r, ExceptionLogRecord)]
        self._begin_write()
        try:
            async with SessionLocal() as db:
                await add_request_logs(db, requests)
                await add_exception_logs(db, exceptions)
                await db.commit()
        except Exception:  # noqa: BLE001 - 审计失败不影响主流程
            logger.exception("批量审计日志写入失败，本批日志丢弃")
        finally:
            self._end_write()

    async def _write_direct(self, record: RequestLogRecord | ExceptionLogRecord) -> None:
        """队列满兜底：复用兼容直写函数（独立会话 + commit）。"""
        try:
            async with SessionLocal() as db:
                if isinstance(record, ExceptionLogRecord):
                    await write_exception_log(
                        db,
                        level=record.level,
                        message=record.message,
                        traceback=record.traceback,
                        request_id=record.request_id,
                        user_id=record.user_id,
                    )
                else:
                    await write_request_log(
                        db,
                        request_id=record.request_id,
                        method=record.method,
                        path=record.path,
                        status_code=record.status_code,
                        user_id=record.user_id,
                        ip_address=record.ip_address,
                        user_agent=record.user_agent,
                        duration_ms=record.duration_ms or 0,
                    )
        except Exception:  # noqa: BLE001 - 日志写入失败不影响主流程
            logger.exception("审计日志兜底直写失败")

    async def _run(self) -> None:
        wakeup = self._wakeup
        if wakeup is None:  # pragma: no cover - start() 保证设置
            return
        while True:
            try:
                # 200ms 内有新日志即提前醒来；超时也强制 drain
                await asyncio.wait_for(wakeup.wait(), timeout=self._flush_interval)
            except TimeoutError:
                pass
            wakeup.clear()  # 先清再取：drain 期间到达的日志会重新置位
            batch = self._take_batch()
            if batch:
                await self._write_batch(batch)
            if self._closing and self._queue.empty():
                break

    async def flush(self) -> None:
        """显式 drain（测试辅助）：把当前队列全部落库并等待在途批次完成。"""
        while True:
            batch = self._take_batch()
            if not batch:
                break
            await self._write_batch(batch)
        await asyncio.to_thread(self._idle.wait, _WRITE_WAIT_TIMEOUT)

    async def close(self) -> None:
        """shutdown：通知写协程收尾，等待其退出后再做最后一次兜底 drain。"""
        self._closing = True
        self._notify()
        task, loop = self._task, self._loop
        if task is not None:
            if loop is asyncio.get_running_loop():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=_WRITE_WAIT_TIMEOUT)
                except TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass
                except asyncio.CancelledError:
                    pass
                except Exception:  # noqa: BLE001
                    logger.exception("审计日志写协程退出异常")
            elif loop is not None and loop.is_running():
                loop.call_soon_threadsafe(task.cancel)
        self._task = None
        self._loop = None
        self._wakeup = None
        await self.flush()


audit_log_writer = AuditLogWriter()


async def flush_audit_logs() -> None:
    """测试辅助：显式等待所有已 enqueue 的日志落库（不依赖 sleep）。"""
    await audit_log_writer.flush()


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
    """请求级审计：request_id 追踪 + enqueue 日志（写入失败不影响主流程）。

    纯 ASGI：应用整链（含异常处理器与依赖 teardown / 事务提交）返回后再入队
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
            state = scope.get("state") or {}
            try:
                await audit_log_writer.enqueue(
                    ExceptionLogRecord(
                        level=LogLevel.ERROR,
                        message=str(exc)[:2000],
                        traceback=traceback.format_exc()[:8000],
                        request_id=request_id,
                        user_id=state.get(REQUEST_STATE_USER_ID),
                    ),
                    required=True,
                )
            except Exception:  # noqa: BLE001 - 入队失败也不能遮盖原异常
                logger.exception("exception_log 入队失败")
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
                    user_agent = _header_of(scope, "user-agent")
                    await audit_log_writer.enqueue(
                        RequestLogRecord(
                            request_id=request_id,
                            method=scope.get("method", ""),
                            path=path,
                            status_code=status_code,
                            user_id=log_user_id,
                            ip_address=resolve_client_ip(Request(scope)),
                            user_agent=user_agent,
                            duration_ms=duration_ms,
                            extra={"device": parse_user_agent(user_agent).model_dump()},
                        ),
                        required=scope.get("method") != "GET",
                    )
            except Exception:  # noqa: BLE001 - 日志 enqueue 失败不影响主流程
                logger.exception("request_log 入队失败")


def _header_of(scope, name: str) -> str | None:
    """从 ASGI scope.headers 取请求头（bytes 列表）。"""
    for key, value in scope.get("headers") or []:
        if key.decode("latin-1").lower() == name:
            return value.decode("latin-1")
    return None


def make_middlewares() -> list:
    """应用中间件列表（按注册顺序生效）。"""
    return [RequestLoggingMiddleware]
