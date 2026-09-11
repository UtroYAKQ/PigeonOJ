"""FPS 题库一键导入端点测试（POST /admin/problems/import，docs/contracts/problems.md）。"""
from __future__ import annotations

import io
import uuid as uuid_mod
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import select

from app.models.problem import Problem, TestCase
from app.models.user import User
from app.core.database import SessionLocal


def _fps_xml(items: list[str]) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<fps>{''.join(items)}</fps>"
    ).encode("utf-8")


def _fps_item(
    title: str,
    *,
    tests: int = 2,
    spj_code: str | None = None,
) -> str:
    test_xml = "".join(
        f"<test_input name='case{i + 1}.in'><![CDATA[{i + 1} 2]]>"
        f"</test_input><test_output name='case{i + 1}.out'><![CDATA[{i + 3}]]></test_output>"
        for i in range(tests)
    )
    spj_xml = f"<spj><![CDATA[{escape(spj_code)}]]></spj>" if spj_code is not None else ""
    return (
        "<item>"
        f"<title>{title}</title>"
        "<time_limit unit='s'>1</time_limit>"
        "<memory_limit unit='mb'>256</memory_limit>"
        "<description><![CDATA[求 A+B]]></description>"
        f"{test_xml}"
        f"{spj_xml}"
        "</item>"
    )


def _zip_bytes(xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("problems/fps.xml", xml)
    return buf.getvalue()


async def _problem_by_title(title: str) -> Problem | None:
    async with SessionLocal() as db:
        return (
            await db.execute(select(Problem).where(Problem.title == title))
        ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_import_zip_creates_published_and_draft(client, admin_headers, fake_storage):
    """有测试点 → published（回填 verified_at）；无测试点 → draft；逐题返回结果。"""
    xml = _fps_xml([_fps_item("FPS 加法"), _fps_item("FPS 无点题", tests=0)])
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("fps.zip", _zip_bytes(xml), "application/zip")},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    data = resp.json()["data"]
    assert data["total_parsed"] == 2
    assert data["imported"] == 2
    assert data["truncated"] is False
    by_title = {item["title"]: item for item in data["results"]}
    assert by_title["FPS 加法"]["status"] == "published"
    pid = by_title["FPS 加法"]["problem_id"]
    assert by_title["FPS 无点题"]["status"] == "draft"

    row = await _problem_by_title("FPS 加法")
    assert row is not None and str(row.id) == pid
    assert len(row.active_case_ids) == 2  # 1 组内嵌 + 2 组 test_input/test_output 对
    assert row.status == "published" and row.verified_at is not None
    assert row.owner_id is not None
    # 测试点内容已落对象存储
    assert any(key.startswith(f"problems/{row.id}/cases/") for key in fake_storage.store)

    draft = await _problem_by_title("FPS 无点题")
    assert draft is not None and draft.status == "draft"


@pytest.mark.asyncio
async def test_import_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("fps.zip", b"PK\x03\x04", "application/zip")},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_rejects_invalid_payload(client, admin_headers):
    """空 XML（非 ZIP 非 fps）→ 1001；ZIP 内无 xml → 1001。"""
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("bad.xml", b"not xml at all", "text/plain")},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no xml here")
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("empty.zip", buf.getvalue(), "application/zip")},
        headers=admin_headers,
    )
    assert resp.json()["code"] == 1001


@pytest.mark.asyncio
async def test_import_duplicate_title_skipped(client, admin_headers, fake_storage):
    xml = _fps_xml([_fps_item("FPS 加法")])
    payload = {"file": ("fps.zip", _zip_bytes(xml), "application/zip")}
    resp = await client.post("/api/v1/admin/problems/import", files=payload, headers=admin_headers)
    assert resp.json()["data"]["imported"] == 1
    resp = await client.post("/api/v1/admin/problems/import", files=payload, headers=admin_headers)
    data = resp.json()["data"]
    assert data["imported"] == 0
    assert data["results"][0]["status"] == "duplicate"


@pytest.mark.asyncio
async def test_import_spj_checker_staged_and_flag_without_source_skipped(
    client, admin_headers, fake_storage,
):
    """<spj> 带源码 → draft_spj + 特判程序写暂存集；仅标记无源码 → skipped_spj。"""
    xml = _fps_xml([
        _fps_item("FPS 特判题", spj_code="int main(){return 0;}"),
        _fps_item("FPS 标记特判", spj_code=""),
    ])
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("fps.zip", _zip_bytes(xml), "application/zip")},
        headers=admin_headers,
    )
    data = resp.json()["data"]
    by_title = {item["title"]: item for item in data["results"]}
    assert by_title["FPS 特判题"]["status"] == "draft_spj"
    assert by_title["FPS 标记特判"]["status"] == "skipped_spj"

    row = await _problem_by_title("FPS 特判题")
    assert row is not None
    assert row.status == "draft"  # 带特判恒为草稿，验题晋升后发布
    assert row.pending_spj_oss_id and row.pending_spj_oss_id in fake_storage.store
    assert row.spj_oss_id is None  # 生效集未动（验题-晋升解耦）


@pytest.mark.asyncio
async def test_import_truncates_over_cap(client, admin_headers, fake_storage, monkeypatch):
    """单次最多尝试 20 题，超出 truncated 标记。"""
    from app.services import problem_import

    monkeypatch.setattr(problem_import, "MAX_IMPORT_ATTEMPTS", 3)
    xml = _fps_xml([_fps_item(f"批量题 {i}") for i in range(5)])
    resp = await client.post(
        "/api/v1/admin/problems/import",
        files={"file": ("fps.zip", _zip_bytes(xml), "application/zip")},
        headers=admin_headers,
    )
    data = resp.json()["data"]
    assert data["total_parsed"] == 5
    assert data["imported"] == 3
    assert data["truncated"] is True


# ---- 导出（GET /admin/problems/{id}/export 与 GET /admin/problems/export） ----


async def _seed_export_problem(
    title: str,
    *,
    with_tests: bool = True,
    with_spj: bool = False,
    fake_storage=None,
) -> str:
    """种子导出用题目：2 个生效测试点（内容入 fake storage）+ 样例 + 可选生效特判。"""
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).limit(1))).scalar_one().id
        spj_key = None
        if with_spj and fake_storage is not None:
            spj_key = f"problems/export-{title}/spj/{uuid_mod.uuid4()}/code"
            fake_storage.store[spj_key] = (b"int main(){return 0;}", "text/x-c++src")
        problem = Problem(
            title=title,
            background="导出测试背景",
            description="求 A+B",
            input_description="一行两个整数",
            output_description="一行输出和",
            note="导出提示",
            samples=[{"input": "1 2", "output": "3"}],
            active_case_ids=[],
            case_status="ok" if with_tests else "empty",
            owner_id=uid,
            status="published",
            visibility="public",
            verified_at=datetime.now(timezone.utc),
            spj_oss_id=spj_key,
        )
        db.add(problem)
        await db.flush()
        case_ids = []
        for i in range(2 if with_tests else 0):
            in_key = f"problems/{problem.id}/cases/{uuid_mod.uuid4()}/input"
            out_key = f"problems/{problem.id}/cases/{uuid_mod.uuid4()}/output"
            if fake_storage is not None:
                fake_storage.store[in_key] = (f"{i + 1} 2\n".encode(), "text/plain")
                fake_storage.store[out_key] = (f"{i + 3}\n".encode(), "text/plain")
            row = TestCase(
                problem_id=problem.id,
                name=f"case{i + 1}",
                input_oss_id=in_key,
                expected_output_oss_id=out_key,
                sort_order=i + 1,
            )
            db.add(row)
            case_ids.append(row)
        await db.flush()
        problem.active_case_ids = [str(row.id) for row in case_ids]
        await db.commit()
        return str(problem.id)


def _parse_items(xml_bytes: bytes) -> list[ET.Element]:
    root = ET.fromstring(xml_bytes)
    assert root.tag == "fps"
    return root.findall("item")


@pytest.mark.asyncio
async def test_export_single_problem_xml(client, admin_headers, fake_storage):
    """单题导出：fps.xml 附件，字段与生效集数据完整（title/limits/样例/测试点/spj）。"""
    pid = await _seed_export_problem(
        "导出单题", with_spj=True, fake_storage=fake_storage,
    )
    resp = await client.get(f"/api/v1/admin/problems/{pid}/export", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/xml")
    assert "attachment" in resp.headers["content-disposition"]
    items = _parse_items(resp.content)
    assert len(items) == 1
    item = items[0]
    assert item.findtext("title") == "导出单题"
    assert item.find("time_limit").get("unit") == "ms"
    assert item.findtext("hint") == "导出提示"
    assert item.findtext("source") == "导出测试背景"
    assert item.findtext("sample_input") == "1 2"
    inputs = item.findall("test_input")
    assert len(inputs) == 2 and inputs[0].get("name") == "case1"
    assert inputs[0].text == "1 2\n"
    assert item.find("spj").text == "int main(){return 0;}"


@pytest.mark.asyncio
async def test_export_batch_zip(client, admin_headers, fake_storage):
    """批量导出：ZIP 内含单文件 fps.xml，一题一 item；缺失 id 跳过。"""
    pid_a = await _seed_export_problem("导出批量甲", fake_storage=fake_storage)
    pid_b = await _seed_export_problem(
        "导出批量乙", with_tests=False, fake_storage=fake_storage,
    )
    resp = await client.get(
        f"/api/v1/admin/problems/export?ids={pid_a},{pid_b},{uuid_mod.uuid4()}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert zf.namelist() == ["fps.xml"]
        items = _parse_items(zf.read("fps.xml"))
    assert len(items) == 2
    titles = {item.findtext("title") for item in items}
    assert titles == {"导出批量甲", "导出批量乙"}
    # 无测试点的题只含样例，不含 test_input
    by_title = {item.findtext("title"): item for item in items}
    assert by_title["导出批量甲"].findall("test_input")
    assert not by_title["导出批量乙"].findall("test_input")
    assert by_title["导出批量乙"].findtext("sample_output") == "3"


@pytest.mark.asyncio
async def test_export_guards(client, admin_headers, user_headers, fake_storage):
    """护栏：全部 id 不存在 → 3001；超 20 题 → 1001；ids 非法 → 1001；普通用户 403。"""
    resp = await client.get(
        f"/api/v1/admin/problems/export?ids={uuid_mod.uuid4()}", headers=admin_headers,
    )
    assert resp.json()["code"] == 3001
    ids = ",".join(str(uuid_mod.uuid4()) for _ in range(21))
    resp = await client.get(f"/api/v1/admin/problems/export?ids={ids}", headers=admin_headers)
    assert resp.json()["code"] == 1001
    resp = await client.get(
        "/api/v1/admin/problems/export?ids=not-a-uuid", headers=admin_headers,
    )
    assert resp.json()["code"] == 1001
    resp = await client.get(
        f"/api/v1/admin/problems/{uuid_mod.uuid4()}/export", headers=user_headers,
    )
    assert resp.status_code == 403
