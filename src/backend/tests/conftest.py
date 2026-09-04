"""pytest 集成测试配置：隔离测试库（pigeonoj_test）+ 隔离 Redis（db 15）。

- 环境变量必须在导入 app 前设置（app.core.database 的引擎在 import 时创建）
- 每次测试会话重建表结构并种子角色 / 配置
- 使用 httpx ASGITransport 走完整 ASGI 链路（含中间件）
"""
from __future__ import annotations

import os

# 测试库：默认 pigeonoj_test；可用 TEST_DATABASE_URL 环境变量覆盖。
# 注意：不要在运行 pytest 时把 DATABASE_URL 指向开发库 —— 测试会 drop_all 重建表！
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj_test"
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "development")

import uuid

import httpx
import pytest_asyncio
from sqlalchemy import select

import app.models.admin  # noqa: F401  (注册到 Base.metadata)
import app.models.contest  # noqa: F401
import app.models.judge  # noqa: F401
import app.models.problem  # noqa: F401
import app.models.team  # noqa: F401
import app.models.user  # noqa: F401
import app.models.audit  # noqa: F401  (平台表：审计日志)
import app.models.system_config  # noqa: F401  (平台表：系统配置)
from app import app
from app.services.system_config import EMAIL_CODE_HTML_TEMPLATE_DEFAULT
from app.models.user import Role, User, UserRole
from app.core.database import Base, SessionLocal, engine
from app.core.redis import get_redis
from app.core.storage import StoredObject
from app.utils.security import hash_password

ROLE_SEEDS = [
    ("11111111-1111-1111-1111-111111111111", "admin", "系统管理员"),
    ("22222222-2222-2222-2222-222222222222", "tutor", "导师"),
    ("33333333-3333-3333-3333-333333333333", "user", "普通用户"),
    ("44444444-4444-4444-4444-444444444444", "team_creator", "团队创建者"),
    ("55555555-5555-5555-5555-555555555555", "team_admin", "团队管理员"),
    ("66666666-6666-6666-6666-666666666666", "team_member", "团队成员"),
]

DEMO_USERS = [
    ("admin@pigeonoj.dev", "Admin@123", "管理员", ["admin"]),
    ("user@pigeonoj.dev", "User@123", "普通用户", ["user"]),
]

CONFIG_SEEDS = [
    ("site", "site.name", "PigeonOJ", "站点名称"),
    ("site", "site.logo", "", "站点 Logo"),
    ("site", "site.icp", "", "ICP 备案号"),
    ("site", "site.default_theme", "light", "默认主题样式"),
    ("site", "site.register_enabled", True, "是否开放注册"),
    ("auth_email", "email.code.expire_seconds", 600, "验证码有效期（秒）"),
    ("auth_email", "email.code.resend_seconds", 60, "验证码重发间隔（秒）"),
    ("auth_email", "email.code.max_attempts", 5, "验证码最大尝试次数"),
    ("auth_email", "email.verify_enabled", True, "注册是否需要邮箱验证码"),
    ("auth_email", "email.smtp.host", "", "SMTP 服务器地址（留空则验证码打印到后端日志）"),
    ("auth_email", "email.smtp.port", 0, "SMTP 端口（0=按 smtp_mode 自动：ssl=465/starttls=587/plain=25）"),
    ("auth_email", "email.smtp.username", "", "SMTP 用户名"),
    ("auth_email", "email.smtp.password", "", "SMTP 密码 / 授权码（管理接口掩码返回）"),
    ("auth_email", "email.smtp.sender", "", "发件人地址（留空用 SMTP 用户名）"),
    ("auth_email", "email.smtp.smtp_mode", "ssl", "SMTP 加密模式（ssl / starttls / plain）"),
    ("auth_email", "email.smtp.use_ssl", True, "（已废弃）旧版是否使用 SSL 直连，存在 smtp_mode 时忽略"),
    ("auth_email", "email.template.code_html", EMAIL_CODE_HTML_TEMPLATE_DEFAULT, "验证码邮件 HTML 正文模板，占位符 {code} / {purpose}（留空用内置默认卡片）"),
    ("team", "invite.expire_hours", 72, "邀请链接有效期（小时）"),
    ("team", "team.apply.review_rule", "manual", "加入审批规则"),
    ("contest", "contest.freeze_default_seconds", 3600, "封榜默认时长（秒）"),
    ("contest", "contest.penalty_factor_minutes", 20, "罚时系数（分钟）"),
    ("sandbox", "sandbox.judge_concurrency", 8, "全局判题并发上限"),
    ("sandbox", "sandbox.cooldown_seconds", 10, "提交冷却时长（秒）"),
    ("log", "log.retention_days", 30, "日志保留天数"),
    ("log", "log.record_get_logs", True, "是否记录 GET 请求日志（关闭后仅记录写操作）"),
    ("community", "community.feature_switches", {"solution": True, "post": True, "comment": True}, "社区功能开关"),
]


@pytest_asyncio.fixture(autouse=True)
async def prepare_db():
    """每个用例重建表结构 + 种子（用例级隔离；async fixture 使用函数级事件循环）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        for rid, code, name in ROLE_SEEDS:
            db.add(Role(id=uuid.UUID(rid), code=code, name=name))
        role_map = {r.code: r.id for r in (await db.execute(select(Role))).scalars().all()}
        for email, password, nickname, role_codes in DEMO_USERS:
            user = User(email=email, password=hash_password(password), nickname=nickname, email_verified=True)
            db.add(user)
            await db.flush()
            for code in role_codes:
                db.add(UserRole(user_id=user.id, role_id=role_map[code], scope="global", object_id=None))
        from app.models.judge import SandboxConfig
        from app.models.system_config import SystemConfig

        for category, key, value, desc in CONFIG_SEEDS:
            db.add(SystemConfig(category=category, config_key=key, config_value=value, description=desc))
        # 沙箱语言配置种子（与 alembic 0004 默认一致；cpp17 为基准）
        for lang, tr, mr, mm, procs in [
            ("python3.12", 3.0, 2.0, 128, 16),
            ("cpp17", 1.0, 1.0, 0, 32),
            ("java21", 2.0, 2.0, 256, 48),
        ]:
            db.add(SandboxConfig(language=lang, time_ratio=tr, memory_ratio=mr, memory_min_mb=mm,
                                 output_limit_kb=1024, cpu_cores=1, process_limit=procs))
        await db.commit()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await (await get_redis()).flushdb()


@pytest_asyncio.fixture
async def client(prepare_db):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await (await get_redis()).flushdb()


async def api_login(client: httpx.AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]["token"]


class FakeStorage:
    """内存对象存储替身（判题/题库测试用）。"""

    def __init__(self):
        self.puts: list[tuple[str, bytes, str]] = []
        self.store: dict[str, tuple[bytes, str]] = {}

    async def put_bytes(self, key, content, content_type):
        self.puts.append((key, content, content_type))
        self.store[key] = (content, content_type)
        return StoredObject(object_key=key, content_type=content_type, size=len(content))

    async def get_bytes(self, key):
        if key not in self.store:
            raise OSError("missing object")
        return self.store[key]

    async def delete(self, key):
        self.store.pop(key, None)


@pytest_asyncio.fixture()
def fake_storage(monkeypatch) -> FakeStorage:
    storage = FakeStorage()
    for target in (
        "app.services.file.get_storage",
        "app.api.v1.files.get_storage",
        "app.services.problem.get_storage",
        "app.services.judge.get_storage",
        "app.rpc.judge_jobs.get_storage",
        "app.rpc.judge_gateway.get_storage",
    ):
        monkeypatch.setattr(target, lambda: storage)
    return storage


@pytest_asyncio.fixture
async def admin_headers(client) -> dict[str, str]:
    token = await api_login(client, "admin@pigeonoj.dev", "Admin@123")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(client) -> dict[str, str]:
    token = await api_login(client, "user@pigeonoj.dev", "User@123")
    return {"Authorization": f"Bearer {token}"}


async def register_user(client: httpx.AsyncClient, email: str, password: str = "Pass@123", nickname: str = "新用户") -> None:
    """验证码固定错误路径使用；正确验证码无法从测试侧获取（开发期打印在日志）。
    本助手通过直接调注册接口 + 直接写 Redis 验证码的方式完成注册闭环。"""
    from app.core.redis import redis_set_json

    await redis_set_json(f"email:code:{email}:register", {"code": "123456", "attempts": 0}, 600)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": "123456", "password": password, "nickname": nickname},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0, resp.text
