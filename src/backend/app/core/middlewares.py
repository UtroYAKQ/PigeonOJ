"""HTTP 中间件：全量请求日志（request_logs）与未处理异常日志（exception_logs）。"""
from __future__ import annotations

import logging
import time
import traceback
import uuid

from fastapi import Request

from app.enums import LogLevel
from app.repositories.audit import write_exception_log, write_request_log
from app.core.database import SessionLocal
from app.core.dependency import REQUEST_STATE_USER_ID
from app.utils.request_meta import resolve_client_ip

logger = logging.getLogger(__name__)


async def request_logging_middleware(request: Request, call_next):
    """请求级审计：request_id 追踪 + 落库（写入失败不影响主流程，docs/contracts/admin.md）。"""
    request_id = uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        # request_id 回传响应头：客户端反馈 / 服务端排障按此关联 request_logs
        response.headers["X-Request-Id"] = request_id
    except Exception as exc:  # noqa: BLE001 - 需记录全部未处理异常
        # 落库异常日志（不阻塞响应）
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
            path = request.url.path
            if len(path) > 512:
                path = path[:512]
            # 认证依赖（_load_user）成功时写入 request.state；匿名请求无此属性 → None
            log_user_id = getattr(request.state, REQUEST_STATE_USER_ID, None)
            async with SessionLocal() as db:
                await write_request_log(
                    db,
                    request_id=request_id,
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    user_id=log_user_id,
                    ip_address=resolve_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    duration_ms=duration_ms,
                )
        except Exception:  # noqa: BLE001 - 日志写入失败不影响主流程
            logger.exception("request_log 写入失败")
    return response


def make_middlewares() -> list:
    """应用中间件列表（按注册顺序生效）。"""
    return [request_logging_middleware]
