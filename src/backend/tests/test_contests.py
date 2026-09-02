"""比赛模块集成测试（docs/contracts/contests.md）。

覆盖：建赛权限与时间校验、报名窗口、赛内访问窗口、ACM/IOI 计分与榜单条件更新、
自动封榜、手动解冻重算（解冻必须人工）、提交记录窗口、赛制快照与原生计分、赛后补题不计榜单。
"""
from __future__ import annotations

import urllib.parse
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.enums import RuleType
from app.models.contest import Contest, ContestProblem, ContestRanking, ContestRegistration
from app.models.judge import Submission, SubmissionTestCaseResult
from app.models.problem import Problem, TestCase
from app.models.user import User
from app.rpc.judge_jobs import CaseOutcome, JudgeOutcome, apply_job_result

from .conftest import api_login, register_user

TUTOR_ROLE_ID = uuid_mod.UUID("22222222-2222-2222-2222-222222222222")


async def _seed_problem(title: str) -> str:
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))).scalar_one().id
        problem = Problem(
            title=title, description="D", owner_id=uid, status="published",
            visibility="public", verified_at=datetime.now(),
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def _tutor_headers(client: httpx.AsyncClient) -> dict[str, str]:
    from app.models.user import UserRole

    email = "tutor@pigeonoj.dev"
    from .conftest import register_user, api_login

    await register_user(client, email)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        db.add(UserRole(user_id=user.id, role_id=TUTOR_ROLE_ID, scope="global", object_id=None))
        await db.commit()
    token = await api_login(client, email, "Pass@123")
    return {"Authorization": f"Bearer {token}"}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _contest_payload(
    *, problems: list[dict], start_offset: int = -3600, end_offset: int = 3600,
    reg_start_offset: int = -7200, reg_end_offset: int = -600,
    freeze_before_end: int = 0, rule: str = "ACM",
) -> dict:
    """时间窗口默认：已开赛 1h、1h 后结束、报名已截止（便于直接赛内提交）。

    freeze_before_end：封榜提前秒数（换算为绝对 freeze_time 时刻；0 = 不封榜）。
    """
    now = datetime.now(timezone.utc)
    start = now + timedelta(seconds=start_offset)
    end = now + timedelta(seconds=end_offset)
    payload = {
        "title": "测试比赛",
        "rule_type": rule,
        "start_time": _iso(start),
        "end_time": _iso(end),
        "register_start_time": _iso(now + timedelta(seconds=reg_start_offset)),
        "register_end_time": _iso(now + timedelta(seconds=reg_end_offset)),
        "problems": problems,
    }
    if freeze_before_end:
        payload["freeze_time"] = _iso(end - timedelta(seconds=freeze_before_end))
    return payload


async def _get_contest_id(client: httpx.AsyncClient, tutor: dict) -> str:
    rows = (await client.get("/api/v1/contests")).json()["data"]["items"]
    return rows[0]["id"]


async def _seed_problem(
    title: str, *, status: str = "published", visibility: str = "public",
    owner_email: str = "admin@pigeonoj.dev",
) -> str:
    """种子题目：published 需带 verified_at（CHECK 约束）。"""
    async with SessionLocal() as db:
        uid = (
            await db.execute(select(User).where(User.email == owner_email))
        ).scalar_one().id
        problem = Problem(
            title=title,
            description="D",
            owner_id=uid,
            status=status,
            visibility=visibility,
            verified_at=datetime.now() if status == "published" else None,
        )
        db.add(problem)
        await db.commit()
        return str(problem.id)


async def test_arrange_own_private_problem(client: httpx.AsyncClient, user_headers) -> None:
    """编排题目可选本人私有题（已发布）；他人私有题拒绝；搜索端点仅管理角色。"""
    tutor = await _tutor_headers(client)
    own_private = await _seed_problem(
        "tutor 私有题", visibility="private", owner_email="tutor@pigeonoj.dev"
    )
    other_private = await _seed_problem(
        "admin 私有题", visibility="private", owner_email="admin@pigeonoj.dev"
    )
    public_p = await _seed_problem("公开赛题")

    payload = _contest_payload(problems=[])
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]

    # 编排：本人私有 + 公开可以，他人私有 → 1001（problems 全量替换走 PUT /contests/{id}）
    resp = await client.put(
        f"/api/v1/contests/{cid}",
        json={"problems": [
            {"problem_id": own_private}, {"problem_id": public_p},
        ]},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    resp = await client.put(
        f"/api/v1/contests/{cid}",
        json={"problems": [{"problem_id": other_private}]},
        headers=tutor,
    )
    assert resp.json()["code"] == 1001

    # 编排搜索端点：返回公开 + 本人私有，不含他人私有
    resp = await client.get(f"/api/v1/contests/{cid}/problems/search", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    titles = {it["title"] for it in resp.json()["data"]["items"]}
    assert "tutor 私有题" in titles and "公开赛题" in titles
    assert "admin 私有题" not in titles

    # 关键字过滤
    resp = await client.get(
        f"/api/v1/contests/{cid}/problems/search?keyword=tutor", headers=tutor
    )
    titles = {it["title"] for it in resp.json()["data"]["items"]}
    assert titles == {"tutor 私有题"}

    # 普通用户调搜索端点 → 2003
    resp = await client.get(f"/api/v1/contests/{cid}/problems/search", headers=user_headers)
    assert resp.json()["code"] == 2003


async def test_create_requires_manager_role(client: httpx.AsyncClient, user_headers) -> None:
    """普通用户建赛 → 2003；tutor 建 → 0，字母自动分配。"""
    p1 = await _seed_problem("比赛题一")
    p2 = await _seed_problem("比赛题二")
    resp = await client.post(
        "/api/v1/contests", json=_contest_payload(problems=[{"problem_id": p1}]), headers=user_headers
    )
    assert resp.json()["code"] == 2003

    tutor = await _tutor_headers(client)
    resp = await client.post(
        "/api/v1/contests",
        json=_contest_payload(problems=[{"problem_id": p1}, {"problem_id": p2, "score": 100}]),
        headers=tutor,
    )
    body = resp.json()
    assert body["code"] == 0, resp.text
    assert body["data"]["problem_count"] == 2

    # 时间非法（报名截止晚于结束）→ 1001
    bad = _contest_payload(problems=[])
    bad["register_end_time"] = bad["end_time"]
    bad["end_time"] = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    resp = await client.post("/api/v1/contests", json=bad, headers=tutor)
    assert resp.json()["code"] == 1001


async def test_register_window(client: httpx.AsyncClient, user_headers) -> None:
    """报名窗口：未开始/已截止 → 3002；窗口内 → 0；重复 → 3003。"""
    p1 = await _seed_problem("报名题")
    tutor = await _tutor_headers(client)
    now = datetime.now(timezone.utc)
    payload = _contest_payload(
        problems=[{"problem_id": p1}],
        start_offset=3600, end_offset=7200,
        reg_start_offset=0, reg_end_offset=1800,
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]

    # 名称关键字搜索（列表中心 keyword 过滤）
    resp = await client.get("/api/v1/contests?keyword=测试")
    items = resp.json()["data"]["items"]
    assert any(it["id"] == cid for it in items)
    resp = await client.get("/api/v1/contests?keyword=不存在的比赛名")
    assert all(it["id"] != cid for it in resp.json()["data"]["items"])

    # 比赛未开始且已报名 → 题目不可见（2003）
    resp = await client.post(f"/api/v1/contests/{cid}/register", headers=user_headers)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/contests/{cid}/problems", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 重复报名 → 3003
    resp = await client.post(f"/api/v1/contests/{cid}/register", headers=user_headers)
    assert resp.json()["code"] == 3003


async def test_contest_access_and_submission_flow(client: httpx.AsyncClient, user_headers) -> None:
    """赛内访问：未报名 2003 / 已报名可看题、交题；赛后自动补题标记。"""
    p1 = await _seed_problem("赛内题")
    tutor = await _tutor_headers(client)
    now = datetime.now(timezone.utc)
    payload = _contest_payload(
        problems=[{"problem_id": p1, "score": 100}],
        start_offset=-600, end_offset=3600, reg_start_offset=-1200, reg_end_offset=-300,
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]

    # 未报名看题 → 2003
    resp = await client.get(f"/api/v1/contests/{cid}/problems", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 报名已截止 → 3002；管理员直接改报名（测试便捷：直接插行）
    resp = await client.post(f"/api/v1/contests/{cid}/register", headers=user_headers)
    assert resp.json()["code"] == 3002
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=uuid_mod.UUID(cid), user_id=uid))
        await db.commit()

    # 看题 + 题目详情统一入口
    resp = await client.get(f"/api/v1/contests/{cid}/problems", headers=user_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"][0]["letter"] == "A"
    resp = await client.get(f"/api/v1/contests/{cid}/problems/{p1}", headers=user_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["id"] == p1

    # 交题（未结束 → 正式比赛提交）
    resp = await client.post(
        f"/api/v1/contests/{cid}/problems/{p1}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0, resp.text
    async with SessionLocal() as db:
        row = (await db.execute(select(Contest).where(Contest.id == uuid_mod.UUID(cid)))).scalar_one()
        from app.models.judge import Submission

        sub = (await db.execute(select(Submission).where(Submission.contest_id == row.id))).scalar_one()
        assert sub.submit_type == "contest"
        assert sub.is_after_contest is False


async def test_contest_submissions_visibility(client: httpx.AsyncClient, user_headers) -> None:
    """提交记录窗口（第 7 条）：管理角色随时可见（含比赛期间）；
    参赛者比赛期间隐藏、赛后开放；未报名用户不可见。"""
    p1 = await _seed_problem("记录窗口题")
    tutor = await _tutor_headers(client)
    payload = _contest_payload(
        problems=[{"problem_id": p1}],
        start_offset=-600, end_offset=3600, reg_start_offset=-1200, reg_end_offset=-300,
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=uuid_mod.UUID(cid), user_id=uid))
        await db.commit()

    resp = await client.post(
        f"/api/v1/contests/{cid}/problems/{p1}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0
    submission_id = resp.json()["data"]["submission_id"]

    # 比赛期间：管理角色可见列表与详情；参赛者不可见
    resp = await client.get(f"/api/v1/contests/{cid}/submissions", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 1 and items[0]["letter"] == "A"
    resp = await client.get(f"/api/v1/contests/{cid}/submissions/{submission_id}", headers=tutor)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/contests/{cid}/submissions", headers=user_headers)
    assert resp.json()["code"] == 2003
    resp = await client.get(f"/api/v1/contests/{cid}/submissions/{submission_id}", headers=user_headers)
    assert resp.json()["code"] == 2003

    # 赛后：已报名可见列表与详情；未报名用户仍不可见
    async with SessionLocal() as db:
        row = await db.get(Contest, uuid_mod.UUID(cid))
        row.end_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        await db.commit()
    resp = await client.get(f"/api/v1/contests/{cid}/submissions", headers=user_headers)
    assert resp.json()["code"] == 0, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 1 and items[0]["letter"] == "A" and items[0]["score"] == 0
    resp = await client.get(f"/api/v1/contests/{cid}/submissions/{submission_id}", headers=user_headers)
    assert resp.json()["code"] == 0
    resp = await client.get(f"/api/v1/contests/{cid}/submissions", headers=tutor)
    assert resp.json()["code"] == 0
    # 未报名（新注册用户）→ 2003
    other = None
    email = "outsider@pigeonoj.dev"
    await register_user(client, email)
    other_token = await api_login(client, email, "Pass@123")
    other = {"Authorization": f"Bearer {other_token}"}
    resp = await client.get(f"/api/v1/contests/{cid}/submissions", headers=other)
    assert resp.json()["code"] == 2003

    # 筛选：昵称关键字 / 语言 / 状态 / 题目
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?keyword={urllib.parse.quote('普通')}",
        headers=user_headers,
    )
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?keyword={urllib.parse.quote('不存在')}",
        headers=user_headers,
    )
    assert resp.json()["data"]["total"] == 0
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?language=cpp17", headers=user_headers
    )
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?language=python3.12", headers=user_headers
    )
    assert resp.json()["data"]["total"] == 0
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?status=accepted", headers=user_headers
    )
    assert resp.json()["data"]["total"] == 0
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?problem_id={p1}", headers=user_headers
    )
    assert resp.json()["data"]["total"] == 1
    resp = await client.get(
        f"/api/v1/contests/{cid}/submissions?problem_id={uuid_mod.uuid4()}",
        headers=user_headers,
    )
    assert resp.json()["data"]["total"] == 0


async def test_acm_ranking_and_manual_unfreeze(client: httpx.AsyncClient, user_headers) -> None:
    """ACM：错误提交计 attempts、首次 AC 计罚时、封榜冻结更新、手动解冻重算。"""
    p1 = await _seed_problem("ACM 榜单题")
    tutor = await _tutor_headers(client)
    now = datetime.now(timezone.utc)
    payload = _contest_payload(
        problems=[{"problem_id": p1}],
        start_offset=-7200, end_offset=3600, reg_start_offset=-10800, reg_end_offset=-5400,
        freeze_before_end=600, rule="ACM",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.commit()
    # 已进入封榜窗口（结束前 1h < 10min? 否）——直接驱动一次 transition 触发不了；手动置冻结
    async with SessionLocal() as db:
        row = await db.get(Contest, cid)
        row.end_time = datetime.now(timezone.utc) + timedelta(seconds=300)
        row.freeze_time = datetime.now(timezone.utc)  # 封榜时间同步（约束 + 立即入封榜窗口）
        await db.commit()

    service_headers = user_headers
    # 两次错误提交
    for _ in range(2):
        resp = await client.post(
            f"/api/v1/contests/{cid}/problems/{p1}/submissions",
            json={"language": "cpp17", "code": "int main(){}"},
            headers=service_headers,
        )
        assert resp.json()["code"] == 0

    # 模拟判题终态：错误 → attempts=2；再 AC → penalty = 分钟差 + 2×20
    async with SessionLocal() as db:
        from app.models.judge import Submission

        subs = list((await db.execute(select(Submission).where(Submission.contest_id == cid))).scalars())
        for s in subs:
            s.status = "wrong_answer"
        await db.commit()
        from app.rpc import judge_jobs  # noqa: F401 - 保证模块已导入

        from app.services.contest import ContestService

        async with SessionLocal() as db2:
            for s in subs:
                await ContestService(db2).update_ranking_on_result(s, "wrong_answer")
            await db2.commit()
    resp = await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)
    board = resp.json()["data"]
    assert board["rows"][0]["cells"][0]["attempts"] == 2

    # 触发自动封榜（结束前 5min < 10min 窗口）
    async with SessionLocal() as db:
        from app.services.contest import ContestService

        async with SessionLocal() as db2:
            await ContestService(db2).transition()
    resp = await client.get(f"/api/v1/contests/{cid}", headers=user_headers)
    assert resp.json()["data"]["board_frozen"] is True

    # 冻结期间错误提交不更新榜单
    async with SessionLocal() as db:
        from app.models.judge import Submission
        from app.services.contest import ContestService

        async with SessionLocal() as db2:
            sub = (await db.execute(select(Submission).where(Submission.contest_id == cid))).scalars().first()
            s2 = Submission(
                user_id=sub.user_id, problem_id=sub.problem_id, language="cpp17", code="x",
                submit_type="contest", contest_id=cid, status="wrong_answer",
            )
            db2.add(s2)
            await db2.commit()
            await ContestService(db2).update_ranking_on_result(s2, "wrong_answer")
            await db2.commit()
    resp = await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)
    assert resp.json()["data"]["rows"][0]["cells"][0]["attempts"] == 2  # 冻结未变

    # 赛中（running）禁止解冻（3002）：封榜是赛时公平机制
    resp = await client.post(f"/api/v1/contests/{cid}/unfreeze", headers=tutor)
    body = resp.json()
    assert body["code"] == 3002, body

    # 比赛结束后才可手动解冻：重算（2 错误 + 1 冻结期错误 → attempts=3）并解除冻结
    async with SessionLocal() as db:
        row = await db.get(Contest, cid)
        row.end_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        row.freeze_time = row.end_time  # 约束：freeze_time <= end_time
        row.status = "finished"
        await db.commit()
    resp = await client.post(f"/api/v1/contests/{cid}/unfreeze", headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    assert resp.json()["data"]["board_frozen"] is False
    resp = await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)
    assert resp.json()["data"]["rows"][0]["cells"][0]["attempts"] == 3

    # 非管理角色解冻 → 2003
    resp = await client.post(f"/api/v1/contests/{cid}/unfreeze", headers=user_headers)
    assert resp.json()["code"] == 2003


async def test_ioi_ranking_takes_max_score(client: httpx.AsyncClient, user_headers) -> None:
    """IOI：每题取历史最高分，多次提交不互相覆盖。"""
    p1 = await _seed_problem("IOI 榜单题")
    tutor = await _tutor_headers(client)
    now = datetime.now(timezone.utc)
    payload = _contest_payload(
        problems=[{"problem_id": p1, "score": 100}],
        start_offset=-7200, end_offset=3600, reg_start_offset=-10800, reg_end_offset=-5400,
        rule="IOI",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.commit()

    from app.models.judge import Submission
    from app.services.contest import ContestService

    async with SessionLocal() as db:
        async with SessionLocal() as db2:
            for score, status in ((30, "wrong_answer"), (80, "wrong_answer"), (55, "wrong_answer")):
                s = Submission(
                    user_id=uid, problem_id=uuid_mod.UUID(p1), language="cpp17", code="x",
                    submit_type="contest", contest_id=cid, status=status, score=score,
                )
                db2.add(s)
                await db2.flush()
                await ContestService(db2).update_ranking_on_result(s, status)
            await db2.commit()
    resp = await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)
    assert resp.json()["data"]["rows"][0]["total_score"] == 80


async def test_contest_rule_type_snapshot_and_after_contest(
    client: httpx.AsyncClient, user_headers
) -> None:
    """赛制快照进提交行（submissions.rule_type）；赛后补题 allowed 且不计榜单。"""
    p1 = await _seed_problem("限分题")
    tutor = await _tutor_headers(client)
    payload = _contest_payload(
        problems=[{"problem_id": p1}],
        start_offset=-7200, end_offset=-3600, reg_start_offset=-10800, reg_end_offset=-5400,
        rule="ACM",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    # 比赛已结束（transition 推进状态）
    async with SessionLocal() as db:
        from app.services.contest import ContestService

        async with SessionLocal() as db2:
            await ContestService(db2).transition()
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.commit()

    # 赛后补题（已结束仍可交，is_after_contest=true）
    resp = await client.post(
        f"/api/v1/contests/{cid}/problems/{p1}/submissions",
        json={"language": "cpp17", "code": "int main(){}"},
        headers=user_headers,
    )
    assert resp.json()["code"] == 0
    async with SessionLocal() as db:
        from app.models.judge import Submission

        sub = (await db.execute(select(Submission).where(Submission.contest_id == cid))).scalar_one()
        assert sub.is_after_contest is True
        # 赛制快照：创建时从所属比赛写入提交行，判题计分按快照派生
        assert sub.rule_type == "ACM"
        # 补题不进榜单
        from app.services.contest import ContestService

        async with SessionLocal() as db2:
            await ContestService(db2).update_ranking_on_result(sub, "accepted")
            await db2.commit()
    resp = await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)
    assert resp.json()["data"]["rows"] == []


async def _seed_case_data(storage, problem_id, *, count: int = 2) -> list[str]:
    """题目补 2 个生效测试点（判题数据写入 fake storage），返回 case_id 列表。"""
    case_ids = [uuid_mod.uuid4() for _ in range(count)]
    async with SessionLocal() as db:
        problem = await db.get(Problem, uuid_mod.UUID(problem_id))
        problem.active_case_ids = [str(c) for c in case_ids]
        problem.case_status = "ok"
        for index, case_id in enumerate(case_ids, start=1):
            db.add(TestCase(
                id=case_id, problem_id=problem.id, name=f"c{index}",
                input_oss_id=f"cases/{case_id}.in",
                expected_output_oss_id=f"cases/{case_id}.out", sort_order=index,
            ))
        await db.commit()
    for case_id in case_ids:
        storage.store[f"cases/{case_id}.in"] = (b"1\n", "text/plain")
        storage.store[f"cases/{case_id}.out"] = (b"2\n", "text/plain")
    return [str(c) for c in case_ids]


async def _seed_contest_with_problem(problem_id: str, *, rule: str, score: int = 100) -> str:
    """直接落库：running 比赛 + 单题编排（IOI 单题分值 score）。"""
    async with SessionLocal() as db:
        owner = (await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))).scalar_one()
        now = datetime.now(timezone.utc)
        contest = Contest(
            title="原生赛制计分赛", owner_id=owner.id, rule_type=rule,
            contest_type="public", start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            register_start_time=now - timedelta(hours=2),
            register_end_time=now - timedelta(minutes=30), status="running",
        )
        db.add(contest)
        await db.flush()
        db.add(ContestProblem(contest_id=contest.id, problem_id=uuid_mod.UUID(problem_id),
                              letter="A", sort_order=0, score=score))
        await db.commit()
        return str(contest.id)


async def _seed_judging_contest_submission(problem_id: str, contest_id: str, *, rule: str) -> str:
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        sub = Submission(user_id=uid, problem_id=uuid_mod.UUID(problem_id),
                         language="cpp17", code="int main(){}", submit_type="contest",
                         contest_id=uuid_mod.UUID(contest_id), rule_type=rule, status="judging")
        db.add(sub)
        await db.commit()
        return str(sub.id)


async def test_acm_binary_scoring_with_short_circuit(fake_storage) -> None:
    """ACM 原生二值计分 + 短路（docs/contracts/judge.md 赛制计分）：

    - 首个测试点失败（节点短路只回传 1 个点）→ 总分 0，仅落已执行点；
    - 全部通过 → 总分 = 单题满分（比赛配置），测试点行不携带分值。
    """
    p1 = await _seed_problem("ACM 二值题")
    case_ids = await _seed_case_data(fake_storage, p1)
    cid = await _seed_contest_with_problem(p1, rule=RuleType.ACM)

    # 短路：节点在点 2 失败后停止，仅回传点 1（accepted）与点 2（wrong_answer）
    sid = await _seed_judging_contest_submission(p1, cid, rule=RuleType.ACM)
    outcome = JudgeOutcome(
        submission_id=sid, status="wrong_answer", time_used_ms=10, memory_used_kb=1024,
        error_message=None,
        cases=(
            CaseOutcome(test_case_id=case_ids[0], status="accepted",
                        time_used_ms=10, memory_used_kb=1024, output=b"2\n"),
            CaseOutcome(test_case_id=case_ids[1], status="wrong_answer",
                        time_used_ms=10, memory_used_kb=1024, output=b"3\n"),
        ),
    )
    async with SessionLocal() as db:
        assert await apply_job_result(db, outcome, storage=fake_storage) is True
    async with SessionLocal() as db:
        sub = await db.get(Submission, uuid_mod.UUID(sid))
        assert sub.score == 0 and sub.status == "wrong_answer"
        rows = list((await db.execute(
            select(SubmissionTestCaseResult).where(SubmissionTestCaseResult.submission_id == sub.id)
        )).scalars())
        assert len(rows) == 2
        assert all(r.score == 0 for r in rows)  # ACM 测试点不设分值

    # 全部通过 → 总分 = 满分 100（ACM 二值）
    sid = await _seed_judging_contest_submission(p1, cid, rule=RuleType.ACM)
    outcome = JudgeOutcome(
        submission_id=sid, status="accepted", time_used_ms=10, memory_used_kb=1024,
        error_message=None,
        cases=tuple(
            CaseOutcome(test_case_id=cid_case, status="accepted",
                        time_used_ms=10, memory_used_kb=1024, output=b"2\n")
            for cid_case in case_ids
        ),
    )
    async with SessionLocal() as db:
        await apply_job_result(db, outcome, storage=fake_storage)
    async with SessionLocal() as db:
        sub = await db.get(Submission, uuid_mod.UUID(sid))
        assert sub.score == 100 and sub.status == "accepted"


async def test_ioi_partial_scoring_unchanged(fake_storage) -> None:
    """IOI 原生部分计分：2 点过 1 点 = 50（满分 100 均分），通过点带分值。"""
    p1 = await _seed_problem("IOI 部分题")
    case_ids = await _seed_case_data(fake_storage, p1)
    cid = await _seed_contest_with_problem(p1, rule=RuleType.IOI)

    sid = await _seed_judging_contest_submission(p1, cid, rule=RuleType.IOI)
    outcome = JudgeOutcome(
        submission_id=sid, status="wrong_answer", time_used_ms=10, memory_used_kb=1024,
        error_message=None,
        cases=(
            CaseOutcome(test_case_id=case_ids[0], status="accepted",
                        time_used_ms=10, memory_used_kb=1024, output=b"2\n"),
            CaseOutcome(test_case_id=case_ids[1], status="wrong_answer",
                        time_used_ms=10, memory_used_kb=1024, output=b"3\n"),
        ),
    )
    async with SessionLocal() as db:
        await apply_job_result(db, outcome, storage=fake_storage)
    async with SessionLocal() as db:
        sub = await db.get(Submission, uuid_mod.UUID(sid))
        assert sub.score == 50 and sub.status == "wrong_answer"



async def test_board_cell_accepted_submissions(client: httpx.AsyncClient, user_headers) -> None:
    """榜单单格成功提交（赛后开放）：仅该 (选手, 题目) 比赛内 AC（不含补题）；比赛期间对所有人隐藏。"""
    p1 = await _seed_problem("榜单格题")
    cid = await _seed_contest_with_problem(p1, rule=RuleType.IOI)
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=uuid_mod.UUID(cid), user_id=uid))
        common = dict(
            user_id=uid, problem_id=uuid_mod.UUID(p1), language="cpp17", code="x",
            submit_type="contest", contest_id=uuid_mod.UUID(cid), rule_type="IOI",
        )
        db.add(Submission(**common, status="wrong_answer"))
        db.add(Submission(**common, status="wrong_answer"))
        ac = Submission(**common, status="accepted")
        db.add(ac)
        db.add(Submission(**common, status="accepted", is_after_contest=True))  # 补题不算「当时」
        await db.commit()
        ac_id, uid_str = str(ac.id), str(uid)

    base = f"/api/v1/contests/{cid}/board/{uid_str}/{p1}/accepted"
    # 比赛期间：所有人不可见（2003）
    resp = await client.get(base, headers=user_headers)
    assert resp.json()["code"] == 2003
    # 结束比赛
    async with SessionLocal() as db:
        row = await db.get(Contest, uuid_mod.UUID(cid))
        row.end_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        await db.commit()
    # 已报名：只含比赛内 AC（1 条），带 letter 映射
    resp = await client.get(base, headers=user_headers)
    assert resp.json()["code"] == 0, resp.text
    items = resp.json()["data"]
    assert len(items) == 1 and items[0]["id"] == ac_id and items[0]["letter"] == "A"
    # 未报名用户 → 2003
    email = "celloutsider@pigeonoj.dev"
    await register_user(client, email)
    token = await api_login(client, email, "Pass@123")
    resp = await client.get(base, headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 2003
    # 题目不在该比赛 → 404
    other_p = await _seed_problem("不在赛内的题")
    resp = await client.get(
        f"/api/v1/contests/{cid}/board/{uid_str}/{other_p}/accepted", headers=user_headers
    )
    assert resp.json()["code"] == 3001

async def test_status_guard_blocks_structural_update(client: httpx.AsyncClient, user_headers) -> None:
    """赛时守卫：running 后 PUT 结构性字段一律 3002；description/logo 同被拒（非白名单语义）。"""
    tutor = await _tutor_headers(client)
    payload = _contest_payload(problems=[])
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]
    # 赛前可编辑
    resp = await client.put(f"/api/v1/contests/{cid}", json={"title": "赛前改名"}, headers=tutor)
    assert resp.json()["code"] == 0, resp.text
    # 驱动周期任务：start_time 已过 → running
    async with SessionLocal() as db:
        from app.services.contest import ContestService

        await ContestService(db).transition()
        await db.commit()
    # 比赛开始后 → 结构性字段拒绝
    resp = await client.put(
        f"/api/v1/contests/{cid}",
        json={"problems": [], "title": "赛中改名"},
        headers=tutor,
    )
    assert resp.json()["code"] == 3002, resp.text
    resp = await client.put(
        f"/api/v1/contests/{cid}", json={"description": "赛中改说明"}, headers=tutor
    )
    assert resp.json()["code"] == 3002, resp.text


async def test_announcement_roundtrip(client: httpx.AsyncClient, user_headers) -> None:
    """公告：赛时可改、详情透出、置空清除；非管理角色 2003。"""
    tutor = await _tutor_headers(client)
    payload = _contest_payload(problems=[])
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/v1/contests/{cid}/announcement",
        json={"announcement": "注意：B 题数据已修正"},
        headers=tutor,
    )
    assert resp.json()["code"] == 0, resp.text

    detail = (await client.get(f"/api/v1/contests/{cid}")).json()["data"]
    assert detail["announcement"] == "注意：B 题数据已修正"
    assert detail["announcement_updated_at"] is not None

    # 置空 = 清除
    resp = await client.put(
        f"/api/v1/contests/{cid}/announcement", json={"announcement": ""}, headers=tutor
    )
    assert resp.json()["code"] == 0
    detail = (await client.get(f"/api/v1/contests/{cid}")).json()["data"]
    assert detail["announcement"] is None

    # 非管理角色 → 2003
    resp = await client.put(
        f"/api/v1/contests/{cid}/announcement", json={"announcement": "x"}, headers=user_headers
    )
    assert resp.json()["code"] == 2003


async def test_scoreboard_show_reveal_order(client: httpx.AsyncClient, user_headers) -> None:
    """滚榜：揭晓序列按「最终名次从差到好」生成，快照榜为起点、最终榜为终点。"""
    p1 = await _seed_problem("滚榜题 A")
    p2 = await _seed_problem("滚榜题 B")
    tutor = await _tutor_headers(client)
    now = datetime.now(timezone.utc)
    payload = _contest_payload(
        problems=[{"problem_id": p1}, {"problem_id": p2}],
        start_offset=-7200, end_offset=600, reg_start_offset=-10800, reg_end_offset=-5400,
        freeze_before_end=300, rule="ACM",
    )
    resp = await client.post("/api/v1/contests", json=payload, headers=tutor)
    cid = uuid_mod.UUID(resp.json()["data"]["id"])
    async with SessionLocal() as db:
        uid = (await db.execute(select(User).where(User.email == "user@pigeonoj.dev"))).scalar_one().id
        db.add(ContestRegistration(contest_id=cid, user_id=uid))
        await db.commit()

    # 选手：封榜前对 A 提交一次错误（回写榜单 → 快照中可见 attempts=1）
    async with SessionLocal() as db:
        from app.services.contest import ContestService

        sub = Submission(
            user_id=uid, problem_id=p1, language="cpp17", code="x",
            submit_type="contest", contest_id=cid, status="wrong_answer",
        )
        db.add(sub)
        await db.commit()
        await ContestService(db).update_ranking_on_result(sub, "wrong_answer")
        await db.commit()
    # 将封榜时间拉到当下以进入封榜窗口，触发 transition 记录 frozen_at
    async with SessionLocal() as db:
        row = await db.get(Contest, cid)
        row.freeze_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    async with SessionLocal() as db:
        from app.services.contest import ContestService

        await ContestService(db).transition()
        await db.commit()

    # 冻结期间的提交：先错后对（时间戳必须晚于 frozen_at=transition 执行瞬间）
    now2 = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        db.add(Submission(
            user_id=uid, problem_id=p1, language="cpp17", code="x",
            submit_type="contest", contest_id=cid, status="wrong_answer",
            created_at=now2 + timedelta(seconds=5),
        ))
        db.add(Submission(
            user_id=uid, problem_id=p1, language="cpp17", code="AC",
            submit_type="contest", contest_id=cid, status="accepted",
            score=100, created_at=now2 + timedelta(seconds=15),
        ))
        await db.commit()

    resp = await client.get(f"/api/v1/contests/{cid}/scoreboard-show", headers=tutor)
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["board_frozen"] is True
    assert data["frozen_at"] is not None

    # 快照榜：A 格冻结、未 AC、封榜前 1 次错误；最终榜：A 通过（attempts=2，1 冻结期错误）
    base_cell = data["base_rows"][0]["cells"][0]
    final_cell = data["final_rows"][0]["cells"][0]
    assert base_cell["accepted"] is False and base_cell["is_frozen"] is True
    assert base_cell["attempts"] == 1
    assert final_cell["accepted"] is True

    # 揭晓序列：全部属于 user（唯一参赛者），AC 在最后一步
    steps = data["steps"]
    assert [s["problem_id"] for s in steps] == [p1, p1], f"steps={steps!r}"
    assert [s["accepted"] for s in steps] == [False, True]
    assert steps[-1]["penalty"] > 0
    # 最终榜与序列终态一致：封榜前 1 错 + 冻结期 1 错
    assert final_cell["attempts"] == 2

    # 非管理角色 → 2003
    resp = await client.get(f"/api/v1/contests/{cid}/scoreboard-show", headers=user_headers)
    assert resp.json()["code"] == 2003
