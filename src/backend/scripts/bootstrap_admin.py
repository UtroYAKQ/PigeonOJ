"""生产环境管理员引导：账号从环境变量读取（.env / compose 注入），幂等可重复执行。

用法（仓库根 .env 配置后，在后端容器或 src/backend 目录执行）：
    BOOTSTRAP_ADMIN_EMAIL=admin@example.com   # 必填
    BOOTSTRAP_ADMIN_PASSWORD=...              # 必填，6~72 位
    BOOTSTRAP_ADMIN_NICKNAME=站长             # 可选，默认取邮箱前缀
    python -m scripts.bootstrap_admin

变量未设置时静默跳过；邮箱已存在时跳过（不覆盖密码）。
开发联调请用 scripts.bootstrap_demo_users（固定演示账号）。
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.exceptions import APIError
from app.models.user import Role, User, UserRole
from app.utils.security import hash_password
from app.utils.validation import validate_email, validate_nickname, validate_password


async def main() -> None:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    nickname = os.environ.get("BOOTSTRAP_ADMIN_NICKNAME", "").strip()

    if not email or not password:
        print("skip  未设置 BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD，跳过管理员引导")
        return

    try:
        validate_email(email)
        validate_password(password)
        if not nickname:
            nickname = email.split("@", 1)[0]
        validate_nickname(nickname)
    except APIError as exc:
        raise SystemExit(f"error {exc.message}") from exc

    async with SessionLocal() as db:
        roles = {r.code: r for r in (await db.execute(select(Role))).scalars().all()}
        admin_role = roles.get("admin")
        if admin_role is None:
            raise SystemExit("error admin 角色不存在：请先执行 alembic upgrade head 完成迁移与种子数据")

        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing is not None:
            print(f"skip  {email}（已存在，不覆盖密码）")
            return

        user = User(email=email, password=hash_password(password), nickname=nickname, email_verified=True)
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=admin_role.id, scope="global", object_id=None))
        await db.commit()
        print(f"create {email} roles=['admin']")


if __name__ == "__main__":
    asyncio.run(main())
