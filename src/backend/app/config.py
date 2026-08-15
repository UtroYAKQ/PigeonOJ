"""全局配置：从环境变量 / .env 加载。

变量清单与 .env.example 对应；本类只做映射，不建立任何外部连接
（数据库 / Redis / MinIO 的连接在后端业务模块中按需初始化）。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- 运行环境 ----
    environment: str = "development"  # development / production
    secret_key: str = "change-me-to-a-random-string"  # 生产环境必改
    log_level: str = "INFO"

    # ---- PostgreSQL ----
    database_url: str = "postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj"

    # ---- Redis / Celery ----
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "pigeonoj"
    minio_secret_key: str = "pigeonoj-minio-secret"
    minio_bucket: str = "pigeonoj"
    minio_secure: bool = False  # 生产（HTTPS）环境置 true

    # ---- CORS ----
    # 开发默认全放行；生产建议改为具体来源列表（JSON 数组形式注入环境变量）
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file="../.env",  # 仓库根目录 .env（本地开发时生效；容器内由 compose env_file 注入）
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中未声明的变量（如 VITE_API_BASE_URL、模型 Key）
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
