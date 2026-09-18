"""验证迁移与种子数据（开发用脚本）。

连接串从统一配置链读取（优先级：进程环境变量 > .env > backend.toml），
不在此硬编码；SQLAlchemy 风格的 `postgresql+asyncpg://` 会自动转成
asyncpg 原生 DSN。
"""
import asyncio

import asyncpg

from app.settings.config import get_settings


def build_dsn() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def main() -> None:
    conn = await asyncpg.connect(build_dsn())
    version = await conn.fetchval("select version_num from alembic_version")
    print("alembic version:", version)
    rows = await conn.fetch(
        "select tablename from pg_tables where schemaname='public' order by tablename"
    )
    print("tables:", ", ".join(r["tablename"] for r in rows))
    roles = await conn.fetchval("select count(*) from roles")
    configs = await conn.fetchval("select count(*) from system_configs")
    print(f"roles={roles} system_configs={configs}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
