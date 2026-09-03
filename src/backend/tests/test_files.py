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
    assert data["oss_id"].startswith("users/")
    assert "/images/" in data["oss_id"]
    assert data["url"] == f"/api/v1/files/{data['oss_id']}"
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
    assert data["oss_id"].startswith("site/logo/")
    assert data["url"] == f"/api/v1/files/{data['oss_id']}"
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
