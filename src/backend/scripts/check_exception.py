"""查询最新的异常日志"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import SessionLocal
from app.models.audit import ExceptionLog
from sqlalchemy import select

async def main():
    async with SessionLocal() as session:
        result = await session.execute(
            select(
                ExceptionLog.level,
                ExceptionLog.message,
                ExceptionLog.traceback,
                ExceptionLog.created_at,
            )
            .order_by(ExceptionLog.created_at.desc())
            .limit(1)
        )
        row = result.first()
        if row:
            print(f"Level: {row.level}")
            print(f"Created: {row.created_at}")
            print(f"Message: {row.message}")
            print(f"\n--- Traceback ---\n{row.traceback}")
        else:
            print("No exception logs found.")

if __name__ == "__main__":
    asyncio.run(main())
