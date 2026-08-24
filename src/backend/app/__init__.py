"""PigeonOJ 后端应用工厂（组合根：唯一允许直接引用各层路由与控制器的位置）。

- 统一响应信封 {code, message, data}（docs/contracts/common.md）
- 全量请求日志 → request_logs（含 request_id 追踪，docs/contracts/admin.md）
- 未处理异常 → exception_logs
- 业务路由统一前缀 /api/v1；判题节点 gRPC 网关（:50051）随应用生命周期启停
- 开发启动：python run.py（等价 uvicorn app:app --reload）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.init_app import lifespan, register_exceptions, register_routers
from app.core.middlewares import request_logging_middleware
from app.log.log import setup_logging
from app.settings.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    _app = FastAPI(title="PigeonOJ API", version="0.1.0", lifespan=lifespan)

    # CORS：开发默认全放行；生产按环境收紧（见 .env.example 与 docs/operations.md）
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 统一异常处理 + 全量请求日志中间件
    register_exceptions(_app)
    _app.middleware("http")(request_logging_middleware)
    # 路由注册（业务前缀 /api/v1 + 系统端点）
    register_routers(_app, prefix="/api/v1")
    return _app


app = create_app()
