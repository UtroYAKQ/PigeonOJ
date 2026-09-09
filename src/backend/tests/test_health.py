"""骨架测试：/health 返回统一信封 {code: 0}。"""
import httpx

# 复用 conftest 的 async client fixture（ASGITransport，跑在会话级事件循环上）：
# 同步 TestClient 每请求在独立线程新 loop 执行 ASGI，判题引擎连接池连接会被
# 绑定到已关闭的 loop，autouse fixture teardown 复用池连接时报 Event loop is closed。
from .conftest import client  # noqa: F401  (re-export 供 pytest fixture 解析)


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"
