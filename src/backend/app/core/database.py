"""异步数据库：引擎 / 会话工厂 / 依赖注入（SQLAlchemy 2.0 + asyncpg）。

连接串来自环境变量 DATABASE_URL（见 app/config.py 与 docs/operations.md）。
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.settings.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类；表结构唯一来源是 alembic/versions/ 下的迁移。"""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：请求级数据库会话；成功提交、异常回滚（Route → Service → Repository 共用）。"""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
