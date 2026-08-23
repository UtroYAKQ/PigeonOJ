"""安全工具：密码哈希（bcrypt）、会话 Token 生成与哈希存储。

安全规则（docs/architecture.md）：密码、会话 Token 哈希存储，不存明文。
"""
from __future__ import annotations

import hashlib
import secrets

import bcrypt


def hash_password(password: str) -> str:
    """bcrypt 哈希密码（自动加盐）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_token() -> str:
    """生成会话 Token（32 字节随机，URL 安全）。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """会话 Token 的 SHA-256 哈希（入库 / Redis key 使用，不存明文）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
