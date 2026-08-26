"""临时探针：复刻真实 pagination 用例并打印中间态（用后即删）。"""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.problem import Problem
from app.core.database import SessionLocal


async def _create_problem(client, admin_headers, **overrides) -> dict:
    payload = {
        "title": "A+B Problem",
        "description": "计算 A+B",
        "input_description": "一行两个整数 A B",
        "output_description": "一行输出 A+B 的值",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/problems", json=payload, headers=admin_headers)
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_probe_pagination_verbatim(client, admin_headers):
    for title in ("Alpha", "Beta", "Alpine"):
        problem = await _create_problem(client, admin_headers, title=title)
        async with SessionLocal() as db:
            row = await db.get(Problem, uuid.UUID(problem["id"]))
            row.status = "published"
            row.verified_at = datetime.now()
            row.published_at = datetime.now()
            await db.commit()
            await db.refresh(row)
            print("SEEDED:", row.title, row.status, row.visibility, row.verified_at)

    async with SessionLocal() as db:
        rows = (
            await db.execute(select(Problem.title, Problem.status, Problem.visibility))
        ).all()
        print("DB ALL:", rows)

    resp = await client.get("/api/v1/problems?page=1&page_size=2")
    body = resp.json()["data"]
    print("TOTAL:", body["total"], [i["title"] for i in body["items"]])
