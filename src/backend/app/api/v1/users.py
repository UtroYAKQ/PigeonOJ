"""用户模块路由：认证（/auth*）+ 用户中心（/users/me*），统一前缀 /api/v1。

原 auth 模块已并入本模块；
API 路径保持不变（docs/contracts/users.md 端点表）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import AuthServiceDep, UserServiceDep
from app.core.dependency import get_bearer_token, get_current_user
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
from app.utils.request_meta import resolve_client_ip
from app.utils.security import hash_token
from app.utils.response import ApiResponse, ok

router = APIRouter()
_auth = APIRouter(prefix="/auth", tags=["auth"])
_users = APIRouter(prefix="/users", tags=["users"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return resolve_client_ip(request), request.headers.get("user-agent")


# ---- 认证 ----


@_auth.post("/email-code", response_model=ApiResponse[None])
async def send_email_code(
    body: EmailCodeRequest,
    request: Request,
    service: AuthServiceDep,
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await service.send_email_code(body, ip, ua)
    return ok(None)


@_auth.post("/register", response_model=ApiResponse[None])
async def register(
    body: RegisterRequest,
    request: Request,
    service: AuthServiceDep,
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await service.register(body, ip, ua)
    return ok(None)


@_auth.post("/login", response_model=ApiResponse[LoginResult])
async def login(
    body: LoginRequest,
    request: Request,
    service: AuthServiceDep,
) -> ApiResponse[LoginResult]:
    ip, ua = _client_meta(request)
    return ok(await service.login(body, ip, ua))


@_auth.post("/logout", response_model=ApiResponse[None])
async def logout(
    request: Request,
    service: AuthServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await service.logout(get_bearer_token(request), current_user, ip, ua)
    return ok(None)


@_auth.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    service: AuthServiceDep,
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await service.reset_password(body, ip, ua)
    return ok(None)


@_auth.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    body: ChangePasswordRequest,
    service: AuthServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    await service.change_password(current_user, body)
    return ok(None)


@_auth.post("/change-email", response_model=ApiResponse[None])
async def change_email(
    body: ChangeEmailRequest,
    request: Request,
    service: AuthServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    ip, ua = _client_meta(request)
    await service.change_email(current_user, body, ip, ua)
    return ok(None)


# ---- 用户中心 ----


@_users.get("/me", response_model=ApiResponse[UserPublic])
async def get_me(
    service: UserServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPublic]:
    return ok(await service.get_me(current_user))


@_users.put("/me", response_model=ApiResponse[UserPublic])
async def update_me(
    patch: ProfileUpdate,
    service: UserServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPublic]:
    return ok(await service.update_profile(current_user, patch))


@_users.delete("/me", response_model=ApiResponse[None])
async def delete_me(
    body: PasswordConfirm,
    service: UserServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    """注销账号（软注销，需密码确认）。"""
    await service.soft_delete(current_user, body.password)
    return ok(None)


@_users.get("/me/sessions", response_model=ApiResponse[list[SessionOut]])
async def list_sessions(
    request: Request,
    service: UserServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[SessionOut]]:
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    return ok(await service.list_sessions(current_user, current_hash))


@_users.delete("/me/sessions/{session_id}", response_model=ApiResponse[None])
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    service: UserServiceDep,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_hash = hash_token(raw_token) if raw_token else ""
    await service.revoke_session(current_user, session_id, current_hash)
    return ok(None)


router.include_router(_auth)
router.include_router(_users)
