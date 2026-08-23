"""Alembic 迁移环境。

表结构唯一来源是迁移 SQL（见 docs/contracts/index.md）。本文件提供
异步连接与 autogenerate 支持；业务表模型随后续各模块逐步接入
target_metadata。
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings

config = context.config

# 连接串：直接以 DATABASE_URL（环境变量 / .env）为准
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 各模块 models.py 在此聚合 import 并赋给 target_metadata，
# 供 `alembic revision --autogenerate` 使用；迁移 SQL 仍为表结构唯一来源。
from app.modules.admin import models as admin_models  # noqa: F401
from app.modules.judge import models as judge_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401
from app.shared.database import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
