"""认证路由（docs/contracts/users.md /auth* 端点，统一前缀 /api/v1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailCodeRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.shared.database import get_db
from app.shared.deps import get_bearer_token, get_current_user, parse_client_ip
from app.shared.response import ok

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return parse_client_ip(request.client.host if request.client else None), request.headers.get("user-agent")


@router.post("/email-code")
async def send_email_code(
    body: EmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).send_email_code(body, ip, ua)
    return ok(None)


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).register(body, ip, ua)
    return ok(None)


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    result = await AuthService(db).login(body, ip, ua)
    return ok(result)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).logout(get_bearer_token(request), current_user, ip, ua)
    return ok(None)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).reset_password(body, ip, ua)
    return ok(None)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).change_password(current_user, body)
    return ok(None)


@router.post("/change-email")
async def change_email(
    body: ChangeEmailRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip, ua = _client_meta(request)
    await AuthService(db).change_email(current_user, body, ip, ua)
    return ok(None)
