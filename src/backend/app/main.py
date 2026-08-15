"""FastAPI 应用入口。

当前为骨架阶段：仅提供 /health 健康检查与统一响应信封，不含业务端点。
业务路由按 docs/contracts/ 各模块契约，在下方「模块路由注册」处逐模块挂载。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.shared.errors import register_exception_handlers
from app.shared.logging import setup_logging
from app.shared.response import ok

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(title="PigeonOJ API", version="0.1.0")

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


# ---- 模块路由注册 ----
# 骨架阶段不实现任何业务端点。后续按 docs/contracts/ 逐模块挂载，例如：
#   from app.modules.auth import routes as auth_routes
#   app.include_router(auth_routes.router, prefix="/api/v1")
