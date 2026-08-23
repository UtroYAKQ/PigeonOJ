"""审计日志写入助手：login_logs / request_logs / exception_logs（docs/contracts/admin.md）。

- 登录日志：auth 流程（login/logout/register/reset_password/change_email）
- 请求日志：由 main.py 中间件全量记录（含 request_id 追踪）
- 异常日志：由 main.py 中间件捕获未处理异常时记录

注意：本模块从 admin/audit.py 上提至 shared 层，解除 auth → admin 的反向依赖。
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import ExceptionLog, LoginLog, RequestLog


async def write_login_log(
    db: AsyncSession,
    action: str,
    success: bool,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
) -> None:
    """写入登录日志（在请求级会话中使用 flush，依赖外层 commit）。"""
    db.add(
        LoginLog(
            user_id=user_id,
            email=email,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            reason=reason,
        )
    )
    await db.flush()


async def write_request_log(
    db: AsyncSession,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    user_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
    duration_ms: int,
) -> None:
    """写入请求日志（在独立会话中使用 commit，确保异常时也能持久化）。"""
    db.add(
        RequestLog(
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            duration_ms=duration_ms,
        )
    )
    await db.commit()


async def write_exception_log(
    db: AsyncSession,
    level: str,
    message: str,
    traceback: str | None,
    request_id: str | None,
    user_id: uuid.UUID | None,
) -> None:
    """写入异常日志（在独立会话中使用 commit，确保异常时也能持久化）。"""
    db.add(
        ExceptionLog(
            level=level,
            message=message,
            traceback=traceback,
            request_id=request_id,
            user_id=user_id,
        )
    )
    await db.commit()
