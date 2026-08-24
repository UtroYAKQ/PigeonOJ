"""应用初始化：生命周期、中间件、异常处理器与路由注册（create_app 组装件）。"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.exceptions import register_exception_handlers
from app.core.middlewares import make_middlewares
from app.core.redis import close_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动判题网关 gRPC 服务与巡检循环，退出时优雅关闭。"""
    from app.controllers import judge_gateway

    grpc_server = await judge_gateway.start_grpc_server()
    maint_task = asyncio.create_task(judge_gateway.maintenance_loop())
    yield
    maint_task.cancel()
    try:
        await maint_task
    except asyncio.CancelledError:
        pass
    if grpc_server is not None:
        await grpc_server.stop(grace=5)
    await close_redis()


def register_exceptions(app: FastAPI) -> None:
    """统一异常处理：业务异常 APIError 与 HTTPException 均转成 {code, message, data} 信封。"""
    register_exception_handlers(app)


def register_routers(app: FastAPI, prefix: str = "/api/v1") -> None:
    """注册业务路由（统一前缀 /api/v1）与系统基础端点。"""
    from app.api.v1 import base
    from app.api.v1 import admin as admin_routes
    from app.api.v1 import files as files_routes
    from app.api.v1 import judge as judge_routes
    from app.api.v1 import problems as problems_routes
    from app.api.v1 import users as users_routes

    # 系统端点：/health 根级、/api/v1/site-config
    app.include_router(base.router)
    app.include_router(base.v1_router)
    # 业务模块路由（统一前缀）
    app.include_router(users_routes.router, prefix=prefix)
    app.include_router(files_routes.router, prefix=prefix)
    app.include_router(problems_routes.router, prefix=prefix)
    app.include_router(judge_routes.router, prefix=prefix)
    app.include_router(admin_routes.router, prefix=prefix)
