"""直接通过 asyncpg 查询最新的异常日志"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://pigeonoj:pigeonoj@localhost:5432/pigeonoj")
    try:
        row = await conn.fetchrow(
            "SELECT level, message, traceback, created_at FROM exception_logs ORDER BY created_at DESC LIMIT 1"
        )
        if row:
            print(f"Level: {row['level']}")
            print(f"Created: {row['created_at']}")
            print(f"Message: {row['message']}")
            print(f"\n--- Traceback ---\n{row['traceback']}")
        else:
            print("No exception logs found.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
