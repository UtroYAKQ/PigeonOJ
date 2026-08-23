"""验证迁移与种子数据（开发用脚本）。"""
import asyncio

import asyncpg

DSN = "postgresql://pigeonoj:pigeonoj@localhost:5432/pigeonoj"


async def main() -> None:
    conn = await asyncpg.connect(DSN)
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
