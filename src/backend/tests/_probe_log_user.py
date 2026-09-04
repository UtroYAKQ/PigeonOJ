"""检查 request_logs 的 user_id 是否被中间件写入（临时探针，跑完即删）。"""
import asyncio


async def main() -> None:
    from sqlalchemy import text

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT r.path, r.user_id, u.nickname "
                    "FROM request_logs r LEFT JOIN users u ON u.id = r.user_id "
                    "ORDER BY r.created_at DESC LIMIT 8"
                )
            )
        ).all()
        for row in rows:
            print(row)


asyncio.run(main())
