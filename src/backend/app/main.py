"""FastAPI 应用入口（组合根：唯一允许直接引用各模块内部路由的位置）。

- 统一响应信封 {code, message, data}（docs/contracts/common.md）
- 全量请求日志 → request_logs（含 request_id 追踪，docs/contracts/admin.md）
- 未处理异常 → exception_logs
- 模块路由：users（认证·用户中心）/ files / problems（题库）/ judge（判题）/ admin
  （统一前缀 /api/v1；跨模块业务调用走各模块 api.py 门面）
- 判题节点 gRPC 网关（:50051）随应用生命周期启停（lifespan）
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.admin import routes as admin_routes
from app.modules.files import routes as files_routes
from app.modules.judge import gateway, routes as judge_routes
from app.modules.problems import routes as problems_routes
from app.modules.users import routes as users_routes
from app.shared.infra.audit import write_exception_log, write_request_log
from app.shared.infra.database import SessionLocal, get_db
from app.modules.users.api import parse_client_ip
from app.shared.common.errors import register_exception_handlers
from app.shared.infra.logging import setup_logging
from app.shared.common.response import ok
from app.shared.infra.redis import close_redis
from app.shared.infra.system_config import get_site_public_configs

logger = logging.getLogger(__name__)

settings = get_settings()
setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动判题网关 gRPC 服务与巡检循环，退出时优雅关闭。"""
    grpc_server = await gateway.start_grpc_server()
    maint_task = asyncio.create_task(gateway.maintenance_loop())
    yield
    maint_task.cancel()
    try:
        await maint_task
    except asyncio.CancelledError:
        pass
    if grpc_server is not None:
        await grpc_server.stop(grace=5)
    await close_redis()


app = FastAPI(title="PigeonOJ API", version="0.1.0", lifespan=lifespan)

# CORS：开发默认全放行；生产按环境收紧（见 .env.example 与 docs/operations.md）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一异常处理：业务异常 APIError 与 HTTPException 均转成 {code, message, data} 信封
register_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """健康检查：返回统一信封 {code: 0, message: "ok", data: {...}}。"""
    return ok({"status": "ok"})


@app.get("/api/v1/site-config", tags=["system"])
async def site_config(db: AsyncSession = Depends(get_db)) -> dict:
    """公开站点配置（未登录可读）：站点名 / Logo / ICP / 默认主题 / 注册开关。"""
    return ok(await get_site_public_configs(db))


# ---- 请求日志中间件（request_logs + exception_logs） ----
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:  # noqa: BLE001 - 需记录全部未处理异常
        # 落库异常日志（不阻塞响应）
        try:
            async with SessionLocal() as db:
                await write_exception_log(
                    db,
                    level="error",
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
            async with SessionLocal() as db:
                await write_request_log(
                    db,
                    request_id=request_id,
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    user_id=None,
                    ip_address=parse_client_ip(request.client.host if request.client else None),
                    user_agent=request.headers.get("user-agent"),
                    duration_ms=duration_ms,
                )
        except Exception:  # noqa: BLE001 - 日志写入失败不影响主流程
            logger.exception("request_log 写入失败")
    return response


# ---- 模块路由注册（统一前缀 /api/v1） ----
app.include_router(users_routes.router, prefix="/api/v1")
app.include_router(files_routes.router, prefix="/api/v1")
app.include_router(problems_routes.router, prefix="/api/v1")
app.include_router(judge_routes.router, prefix="/api/v1")
app.include_router(admin_routes.router, prefix="/api/v1")
