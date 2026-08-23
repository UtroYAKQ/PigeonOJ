"""异步数据库（兼容层，已迁移至 shared/infra/database.py）。

保留此文件以兼容旧有导入：
    from app.shared.database import get_db, SessionLocal, Base

新代码请直接使用：
    from app.shared.infra.database import get_db, SessionLocal, Base
"""
from app.shared.infra.database import Base, SessionLocal, get_db  # noqa: F401

__all__ = ["Base", "SessionLocal", "get_db"]
