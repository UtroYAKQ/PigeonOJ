"""代码广场集成测试：分享生命周期、管理端点、功能开关与评论目标拒绝
（docs/contracts/community.md「代码广场」；分享不关联题目、不设评论）。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.system_config import SystemConfig
from .test_community import _flush_redis, _user_headers


async def _create_share(client, headers, **overrides) -> dict:
    payload = {
        "title": "快速排序模板",
        "language": "cpp17",
        "code": "void quick_sort(int *a, int l, int r) { /* ... */ }",
        "description": "手写快排模板，背下来就能用。",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/codes", json=payload, headers=headers)
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


async def _set_switch(**switches) -> None:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(SystemConfig).where(
                    SystemConfig.category == "community",
                    SystemConfig.config_key == "community.feature_switches",
                )
            )
        ).scalar_one()
        row.config_value = {"solutions": True, "comments": True, **switches}
        await db.commit()


@pytest.mark.asyncio
async def test_code_share_lifecycle(client, admin_headers, user_headers):
    share = await _create_share(client, user_headers)
    sid = share["id"]
    assert share["status"] == "published"
    assert share["language"] == "cpp17"
    assert share["author"]["nickname"] == "普通用户"

    # 频控 60s：第二个分享 4002，清 Redis 后继续
    resp = await client.post(
        "/api/v1/codes",
        json={"title": "x", "language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 4002
    await _flush_redis()

    # 列表 published 可见；详情含代码原文
    resp = await client.get("/api/v1/codes")
    body = resp.json()["data"]
    assert body["total"] == 1
    resp = await client.get(f"/api/v1/codes/{sid}")
    assert "quick_sort" in resp.json()["data"]["code"]

    # 非法语言 1001；空白代码 1001
    resp = await client.post(
        "/api/v1/codes",
        json={"title": "x", "language": "rust", "code": "fn main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 1001
    resp = await client.post(
        "/api/v1/codes",
        json={"title": "x", "language": "cpp17", "code": "   "},
        headers=user_headers,
    )
    assert resp.json()["code"] == 1001

    # owner 删除（软下架）→ 匿名 404，作者可读；admin 恢复
    resp = await client.delete(f"/api/v1/codes/{sid}", headers=user_headers)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/codes/{sid}")
    assert resp.json()["code"] == 3001
    resp = await client.get(f"/api/v1/codes/{sid}", headers=user_headers)
    assert resp.json()["data"]["status"] == "removed"
    resp = await client.put(
        f"/api/v1/admin/codes/{sid}/status", json={"status": "published"}, headers=admin_headers
    )
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/codes/{sid}")
    assert resp.json()["code"] == 0

    # 他人删除 2003
    other = await _user_headers(client, "coder2@pigeonoj.dev")
    await _flush_redis()
    resp = await client.post(
        "/api/v1/codes",
        json={"title": "别人的分享", "language": "python3.12", "code": "print(1)"},
        headers=other,
    )
    other_sid = resp.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/codes/{other_sid}", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 管理列表（全状态 + 语言筛选）
    resp = await client.get("/api/v1/admin/codes", headers=admin_headers)
    body = resp.json()["data"]
    assert body["total"] == 2
    assert {row["language"] for row in body["items"]} == {"cpp17", "python3.12"}
    resp = await client.get("/api/v1/admin/codes", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 分享不设评论：code_share 目标一律 1001
    resp = await client.post(
        "/api/v1/comments",
        json={"target_type": "code_share", "target_id": sid, "content": "收藏了"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 1001

    # 举报目标存在性：code_share 可举报、重复 3003；admin 举报列表摘要回填
    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "code_share", "target_id": sid, "reason": "抄袭"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0
    resp = await client.post(
        "/api/v1/reports",
        json={"target_type": "code_share", "target_id": sid, "reason": "再报"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 3003
    resp = await client.get("/api/v1/admin/reports", headers=admin_headers)
    items = resp.json()["data"]["items"]
    assert any(item["target_type"] == "code_share" and item["target_summary"] for item in items)


@pytest.mark.asyncio
async def test_code_share_feature_switch(client, admin_headers, user_headers):
    """codes 开关关闭：创建 / 删除 3002，浏览不受影响。"""
    share = await _create_share(client, admin_headers)
    await _set_switch(codes=False)

    resp = await client.post(
        "/api/v1/codes",
        json={"title": "开关关闭", "language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 3002
    resp = await client.get("/api/v1/codes")
    assert resp.json()["code"] == 0
    resp = await client.delete(f"/api/v1/codes/{share['id']}", headers=admin_headers)
    assert resp.json()["code"] == 3002

    await _set_switch(codes=True)
    resp = await client.delete(f"/api/v1/codes/{share['id']}", headers=admin_headers)
    assert resp.json()["code"] == 0
