"""用户中心路由（docs/contracts/users.md /users/me* 端点，统一前缀 /api/v1）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.schemas import PasswordConfirm, ProfileUpdate
from app.modules.users.service import UserService
from app.shared.database import get_db
from app.shared.deps import get_current_user
from app.shared.response import ok
from app.shared.security import hash_token
from app.modules.users.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return ok((await service.get_me(current_user)).model_dump(mode="json"))


@router.put("/me")
async def update_me(
    patch: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return ok((await service.update_profile(current_user, patch)).model_dump(mode="json"))


@router.delete("/me")
async def delete_me(
    body: PasswordConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注销账号（软注销，需密码确认）。"""
    service = UserService(db)
    await service.soft_delete(current_user, body.password)
    return ok(None)


@router.get("/me/sessions")
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    return ok(await service.list_sessions(current_user, current_hash))


@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    await service.revoke_session(current_user, session_id, current_hash)
    return ok(None)
