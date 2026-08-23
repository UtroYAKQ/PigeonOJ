"""全局配置：从环境变量 / .env 加载。

变量清单与 .env.example 对应；本类只做映射，不建立任何外部连接
（数据库 / Redis / MinIO 的连接在后端业务模块中按需初始化）。
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- 运行环境 ----
    environment: str = "development"  # development / production
    secret_key: str = "change-me-to-a-random-string"  # 生产环境必改
    log_level: str = "INFO"

    # ---- PostgreSQL ----
    database_url: str = "postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "pigeonoj"
    minio_secret_key: str = "pigeonoj-minio-secret"
    minio_bucket: str = "pigeonoj"
    minio_secure: bool = False  # 生产（HTTPS）环境置 true

    # ---- 判题节点网关（docs/contracts/judge.md 节点网关协议）----
    # 后端不执行任何用户代码；代码执行只发生在注册的判题节点容器内。
    # 注册令牌（逗号分隔多个）；为空则网关不启动。判题节点凭其一完成注册。
    judge_gateway_tokens: str = ""
    judge_grpc_host: str = "0.0.0.0"
    judge_grpc_port: int = 50051
    judge_heartbeat_interval_seconds: int = 10

    @property
    def gateway_tokens(self) -> list[str]:
        return [item.strip() for item in self.judge_gateway_tokens.split(",") if item.strip()]

    @field_validator(
        "database_url", "redis_url", "minio_endpoint", mode="before"
    )
    @classmethod
    def _strip_url_whitespace(cls, v: object) -> object:
        """去除连接串首尾空白：cmd 中 `set VAR=...` 行尾误带空格会污染值（如 database "pigeonoj "）。"""
        return v.strip() if isinstance(v, str) else v

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
