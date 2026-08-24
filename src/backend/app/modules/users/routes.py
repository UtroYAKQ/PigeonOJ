"""用户模块路由：认证（/auth*）+ 用户中心（/users/me*），统一前缀 /api/v1。

原 auth 模块已并入本模块（docs/decisions/2026-08-24-backend-module-packaging.md）；
API 路径保持不变（docs/contracts/users.md 端点表）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.deps import get_bearer_token, get_current_user, parse_client_ip
from app.modules.users.models import User
from app.modules.users.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailCodeRequest,
    LoginRequest,
    PasswordConfirm,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.modules.users.service import AuthService, UserService
from app.shared.auth.security import hash_token
from app.shared.common.response import ok
from app.shared.infra.database import get_db

router = APIRouter()
_auth = APIRouter(prefix="/auth", tags=["auth"])
_users = APIRouter(prefix="/users", tags=["users"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return parse_client_ip(request.client.host if request.client else None), request.headers.get("user-agent")


# ---- 认证 ----


@_auth.post("/email-code")
async def send_email_code(
    body: EmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).send_email_code(body, ip, ua)
    return ok(None)


@_auth.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).register(body, ip, ua)
    return ok(None)


@_auth.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    result = await AuthService(db).login(body, ip, ua)
    return ok(result)


@_auth.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).logout(get_bearer_token(request), current_user, ip, ua)
    return ok(None)


@_auth.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).reset_password(body, ip, ua)
    return ok(None)


@_auth.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).change_password(current_user, body)
    return ok(None)


@_auth.post("/change-email")
async def change_email(
    body: ChangeEmailRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).change_email(current_user, body, ip, ua)
    return ok(None)


# ---- 用户中心 ----


@_users.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return ok((await service.get_me(current_user)).model_dump(mode="json"))


@_users.put("/me")
async def update_me(
    patch: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return ok((await service.update_profile(current_user, patch)).model_dump(mode="json"))


@_users.delete("/me")
async def delete_me(
    body: PasswordConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注销账号（软注销，需密码确认）。"""
    service = UserService(db)
    await service.soft_delete(current_user, body.password)
    return ok(None)


@_users.get("/me/sessions")
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    return ok(await service.list_sessions(current_user, current_hash))


@_users.delete("/me/sessions/{session_id}")
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


router.include_router(_auth)
router.include_router(_users)
