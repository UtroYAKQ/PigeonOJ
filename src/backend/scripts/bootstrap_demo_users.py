"""引导演示账号（开发用）：admin / tutor / user，与前端 Mock 演示账号一致。

用法：python -m scripts.bootstrap_demo_users
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.models.user import Role, User, UserRole
from app.core.database import SessionLocal
from app.utils.security import hash_password

DEMO_USERS = [
    ("admin@pigeonoj.dev", "Admin@123", "鸽子管理员", ["admin"]),
    ("tutor@pigeonoj.dev", "Tutor@123", "导师老白", ["tutor"]),
    ("user@pigeonoj.dev", "User@123", "萌新小鸽", ["user"]),
]


async def main() -> None:
    async with SessionLocal() as db:
        roles = {r.code: r for r in (await db.execute(select(Role))).scalars().all()}
        for email, password, nickname, role_codes in DEMO_USERS:
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing is not None:
                print(f"skip  {email}（已存在）")
                continue
            user = User(email=email, password=hash_password(password), nickname=nickname, email_verified=True)
            db.add(user)
            await db.flush()
            for code in role_codes:
                role = roles.get(code)
                if role:
                    db.add(UserRole(user_id=user.id, role_id=role.id, scope="global", object_id=None))
            print(f"create {email} roles={role_codes}")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
