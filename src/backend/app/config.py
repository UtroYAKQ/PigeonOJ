"""全局配置：src/backend/backend.toml 为唯一配置文件，.env / 环境变量可覆盖。

优先级（高 → 低）：进程环境变量 > .env > backend.toml。
本类只做映射，不建立任何外部连接
（数据库 / Redis / MinIO 的连接在后端业务模块中按需初始化）。
"""
from functools import lru_cache
from pathlib import Path

import tomllib

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

# backend 目录：config.py 位于 src/backend/app/ 下，向上一级即 src/backend（与 CWD 无关）
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
# 仓库根目录：.env 约定位置（docs/operations.md）
_REPO_ROOT = _BACKEND_ROOT.parent.parent


class FlatTomlSource(TomlConfigSettingsSource):
    """读取 backend.toml 并把 [section] key 拍平为扁平字段名。

    规则：section_key 是字段则加前缀（[minio] endpoint → minio_endpoint），
    否则用裸键名（[app] environment → environment）。
    """

    def __init__(self, settings_cls: type[BaseSettings], **kwargs) -> None:
        # 父类在 super().__init__ 之前就读文件，字段集合需先行取出
        self._field_names = frozenset(settings_cls.model_fields)
        super().__init__(settings_cls, **kwargs)

    def _read_file(self, file_path: Path) -> dict:
        with open(file_path, "rb") as fh:
            data = tomllib.load(fh)
        flat: dict = {}
        for section, value in data.items():
            if isinstance(value, dict):
                for key, item in value.items():
                    flat[f"{section}_{key}" if f"{section}_{key}" in self._field_names else key] = item
            else:
                flat[section] = value
        return flat


class Settings(BaseSettings):
    # ---- 运行环境 ----
    environment: str  # development / production
    secret_key: str  # 生产环境必改
    log_level: str

    # ---- PostgreSQL ----
    database_url: str

    # ---- Redis ----
    redis_url: str

    # ---- MinIO ----
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool

    # ---- 判题节点网关（docs/contracts/judge.md 节点网关协议）----
    # 注册令牌（逗号分隔多个）；为空则网关不启动。判题节点凭其一完成注册。
    judge_gateway_tokens: str
    judge_grpc_host: str
    judge_grpc_port: int
    judge_heartbeat_interval_seconds: int

    # ---- CORS ----
    cors_origins: list[str]

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

    model_config = SettingsConfigDict(
        # .env 候选路径：文档约定为仓库根目录；../ 与 ./ 兼容历史 CWD 约定
        env_file=("../.env", ".env", _REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略未声明的变量（如 VITE_API_BASE_URL、模型 Key、POSTGRES_USER）
        # TOML 候选路径（_read_files 逐个尝试，存在即加载）：
        # 本地开发 cwd=src/backend 或容器 WORKDIR=/app → ./；任意 CWD 兜底 → 按源码定位 backend 目录
        toml_file=("backend.toml", _BACKEND_ROOT / "backend.toml"),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # 元组顺序即优先级：靠前覆盖靠后
        return (init_settings, env_settings, dotenv_settings, FlatTomlSource(settings_cls), file_secret_settings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
