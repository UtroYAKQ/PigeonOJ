"""用户模块路由：认证（/auth*）+ 用户中心（/users/me*），统一前缀 /api/v1。

原 auth 模块已并入本模块（docs/decisions/2026-08-24-backend-module-packaging.md）；
API 路径保持不变（docs/contracts/users.md 端点表）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency import get_bearer_token, get_current_user, parse_client_ip
from app.models.user import User
from app.schemas.user import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailCodeRequest,
    LoginRequest,
    LoginResult,
    PasswordConfirm,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    UserPublic,
)
from app.services.user import AuthService, UserService
from app.utils.security import hash_token
from app.utils.response import ApiResponse, ok
from app.core.database import get_db

router = APIRouter()
_auth = APIRouter(prefix="/auth", tags=["auth"])
_users = APIRouter(prefix="/users", tags=["users"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return parse_client_ip(request.client.host if request.client else None), request.headers.get("user-agent")


# ---- 认证 ----


@_auth.post("/email-code", response_model=ApiResponse[None])
async def send_email_code(
    body: EmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await AuthService(db).send_email_code(body, ip, ua)
    return ok(None)


@_auth.post("/register", response_model=ApiResponse[None])
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await AuthService(db).register(body, ip, ua)
    return ok(None)


@_auth.post("/login", response_model=ApiResponse[LoginResult])
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LoginResult]:
    ip, ua = _client_meta(request)
    return ok(await AuthService(db).login(body, ip, ua))


@_auth.post("/logout", response_model=ApiResponse[None])
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await AuthService(db).logout(get_bearer_token(request), current_user, ip, ua)
    return ok(None)


@_auth.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await AuthService(db).reset_password(body, ip, ua)
    return ok(None)


@_auth.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    await AuthService(db).change_password(current_user, body)
    return ok(None)


@_auth.post("/change-email", response_model=ApiResponse[None])
async def change_email(
    body: ChangeEmailRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await AuthService(db).change_email(current_user, body, ip, ua)
    return ok(None)


# ---- 用户中心 ----


@_users.get("/me", response_model=ApiResponse[UserPublic])
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserPublic]:
    return ok(await UserService(db).get_me(current_user))


@_users.put("/me", response_model=ApiResponse[UserPublic])
async def update_me(
    patch: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserPublic]:
    return ok(await UserService(db).update_profile(current_user, patch))


@_users.delete("/me", response_model=ApiResponse[None])
async def delete_me(
    body: PasswordConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """注销账号（软注销，需密码确认）。"""
    await UserService(db).soft_delete(current_user, body.password)
    return ok(None)


@_users.get("/me/sessions", response_model=ApiResponse[list[SessionOut]])
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[SessionOut]]:
    service = UserService(db)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    return ok(await service.list_sessions(current_user, current_hash))


@_users.delete("/me/sessions/{session_id}", response_model=ApiResponse[None])
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    service = UserService(db)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    await service.revoke_session(current_user, session_id, current_hash)
    return ok(None)


router.include_router(_auth)
router.include_router(_users)
