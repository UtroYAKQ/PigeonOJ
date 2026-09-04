"""公共图片上传接口测试（POST /files/upload/image + GET /files/{key}）。"""
from __future__ import annotations

import httpx

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-content"


async def test_upload_image_requires_auth(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/v1/files/upload/image",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 401, resp.text


async def test_upload_image_success_and_read_back(client, user_headers, fake_storage):
    resp = await client.post(
        "/api/v1/files/upload/image",
        headers=user_headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["url"].startswith("/api/v1/files/users/")
    assert "/images/" in data["url"]
    assert data["content_type"] == "image/png"
    assert data["size"] == len(PNG_BYTES)

    # 上传对象可经公开读取接口读回（users/ 前缀白名单）
    read = await client.get(data["url"])
    assert read.status_code == 200
    assert read.content == PNG_BYTES
    assert read.headers["content-type"].startswith("image/png")


async def test_upload_image_rejects_non_image(client, user_headers):
    resp = await client.post(
        "/api/v1/files/upload/image",
        headers=user_headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    body = resp.json()
    assert body["code"] == 1001
    assert "JPG" in body["message"]


async def test_upload_image_rejects_oversize(client, user_headers):
    big = PNG_BYTES + b"0" * (5 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/files/upload/image",
        headers=user_headers,
        files={"file": ("a.png", big, "image/png")},
    )
    body = resp.json()
    assert body["code"] == 1001
    assert "5MB" in body["message"]


async def test_upload_site_logo_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/files/upload/site-logo",
        headers=user_headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 403, resp.text


async def test_upload_site_logo_requires_auth(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/v1/files/upload/site-logo",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 401, resp.text


async def test_upload_site_logo_success_and_read_back(client, admin_headers, fake_storage):
    resp = await client.post(
        "/api/v1/files/upload/site-logo",
        headers=admin_headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["url"].startswith("/api/v1/files/site/logo/")
    assert data["content_type"] == "image/png"
    assert data["size"] == len(PNG_BYTES)

    # site/logo/ 前缀经公开读取白名单可读回
    read = await client.get(data["url"])
    assert read.status_code == 200
    assert read.content == PNG_BYTES
    assert read.headers["content-type"].startswith("image/png")


async def test_upload_site_logo_rejects_non_image(client, admin_headers):
    resp = await client.post(
        "/api/v1/files/upload/site-logo",
        headers=admin_headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    body = resp.json()
    assert body["code"] == 1001
    assert "JPG" in body["message"]


async def test_upload_avatar_store_full_site_url_and_read_back(client, user_headers, fake_storage):
    """用户头像：上传返回站内完整 URL，直接存库并可原样读回（与团队/比赛头像同构）。"""
    resp = await client.post(
        "/api/v1/files/upload/avatar",
        headers=user_headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].startswith("/api/v1/files/users/")
    assert "/avatar/" in data["url"]

    # 前端直接使用上传返回的 url 存库（docs/contracts/users.md）
    upd = await client.put(
        "/api/v1/users/me",
        headers=user_headers,
        json={"nickname": "普通用户", "avatar_url": data["url"]},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["avatar_url"] == data["url"]

    # 存储的完整 URL 可原样读回
    read = await client.get(data["url"])
    assert read.status_code == 200
    assert read.content == PNG_BYTES
