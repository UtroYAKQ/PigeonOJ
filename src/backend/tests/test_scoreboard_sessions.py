"""Resolver endpoints against the isolated PostgreSQL integration database."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.contest import Contest, ContestRegistration, ScoreboardSession
from app.models.judge import Submission
from app.models.user import User
from app.services.contest import ContestService

from .test_contests import _contest_payload, _seed_problem


async def seed(client, admin):
    problem_id = uuid.UUID(await _seed_problem("Resolver"))
    payload = _contest_payload(problems=[{"problem_id": str(problem_id)}], start_offset=-21600,
        end_offset=-60, reg_start_offset=-25000, reg_end_offset=-22000, freeze_before_end=3600)
    response = await client.post("/api/v1/contests", json=payload, headers=admin)
    assert response.status_code == 200, response.text
    cid = uuid.UUID(response.json()["data"]["id"])
    async with SessionLocal() as db:
        contest = await db.get(Contest, cid)
        contest.status = "finished"
        contest.board_frozen = True
        contest.frozen_at = contest.freeze_time + timedelta(seconds=5)
        uid = (await db.execute(select(User.id).where(User.email == "user@pigeonoj.dev"))).scalar_one()
        admin_id = (await db.execute(select(User.id).where(User.email == "admin@pigeonoj.dev"))).scalar_one()
        db.add_all([ContestRegistration(contest_id=cid, user_id=uid), ContestRegistration(contest_id=cid, user_id=admin_id)])
        submissions = []
        for offset, status in [(1200, "wrong_answer"), (18500, "wrong_answer"), (19000, "accepted")]:
            sub = Submission(contest_id=cid, user_id=uid, problem_id=problem_id, submit_type="contest", language="cpp17",
                code="int main(){}", status=status, score=100 if status == "accepted" else 0,
                created_at=contest.start_time + timedelta(seconds=offset))
            db.add(sub)
            submissions.append(sub)
        await db.commit()
        return cid, uid, problem_id, [s.id for s in submissions]


def command(revision, action="next", command_id=None, speed=1):
    return dict(revision=revision, action=action, command_id=str(command_id or uuid.uuid4()), speed=speed)


async def test_create_progress_conflicts_duplicates_and_immutable_snapshot(client, admin_headers, user_headers):
    cid, uid, pid, submissions = await seed(client, admin_headers)
    path = f"/api/v1/contests/{cid}/scoreboard-session"
    created = (await client.post(path, headers=admin_headers)).json()["data"]
    again = (await client.post(path, headers=admin_headers)).json()["data"]
    assert again["id"] == created["id"] and created["cursor"] == 0
    assert created["total_steps"] == 2
    assert len(created["rows"]) == 2  # Includes a registered account without submissions.
    assert not {"snapshot", "steps", "final_rows"}.intersection(created)
    assert all(set(problem) == {"problem_id", "letter", "score", "sort_order"} for problem in created["problems"])
    viewer = (await client.get(path, headers=user_headers)).json()["data"]
    assert not viewer["can_control"] and viewer["rows"] == created["rows"]
    body = command(0)
    forbidden = await client.post(path + "/commands", headers=user_headers, json=body)
    assert forbidden.status_code == 403
    first = (await client.post(path + "/commands", headers=admin_headers, json=body)).json()["data"]
    duplicate = (await client.post(path + "/commands", headers=admin_headers, json=body)).json()["data"]
    assert first["cursor"] == duplicate["cursor"] == 1 and duplicate["revision"] == 1
    stale = await client.post(path + "/commands", headers=admin_headers, json=command(0))
    assert stale.status_code == 409
    concurrent = await asyncio.gather(*[client.post(path + "/commands", headers=admin_headers, json=command(1)) for _ in range(2)])
    assert sorted(r.status_code for r in concurrent) == [200, 409]
    audience1 = (await client.get(path, headers=user_headers)).json()["data"]
    audience2 = (await client.get(path, headers=user_headers)).json()["data"]
    assert audience1["rows"] == audience2["rows"] and audience1["cursor"] == 2
    assert next(r for r in audience1["rows"] if r["user_id"] == str(uid))["cells"][0]["accepted"]
    async with SessionLocal() as db:
        sub = await db.get(Submission, submissions[-1])
        sub.status = "wrong_answer"
        await db.commit()
    # A rejudge cannot silently modify the session's stored snapshot.
    after = (await client.get(path, headers=user_headers)).json()["data"]
    assert after["rows"] == audience1["rows"]
    prepared = (await client.post(path + "/commands", headers=admin_headers, json=command(2, "prepare"))).json()["data"]
    assert prepared["id"] != after["id"] and prepared["cursor"] == 0 and prepared["revision"] == 3
    assert (await client.get(f"/api/v1/contests/{cid}", headers=admin_headers)).json()["data"]["board_frozen"]


async def test_server_clock_continues_without_controller_and_refresh_recovers(client, admin_headers, user_headers):
    cid, *_ = await seed(client, admin_headers)
    path = f"/api/v1/contests/{cid}/scoreboard-session"
    await client.post(path, headers=admin_headers)
    played = await client.post(path + "/commands", headers=admin_headers, json=command(0, "play"))
    assert played.json()["data"]["playing"]
    speed = await client.post(path + "/commands", headers=admin_headers, json=command(1, "speed", speed=4))
    assert speed.json()["data"]["playing"] and speed.json()["data"]["speed"] == 4
    async with SessionLocal() as db:
        session = (await db.execute(select(ScoreboardSession).where(ScoreboardSession.contest_id == cid))).scalar_one()
        session.anchor_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        await db.commit()
    finished = (await client.get(path, headers=user_headers)).json()["data"]
    refreshed = (await client.get(path, headers=user_headers)).json()["data"]
    assert finished["cursor"] == finished["total_steps"] and not finished["playing"]
    assert refreshed["rows"] == finished["rows"]
    assert (await client.get(f"/api/v1/contests/{cid}/board", headers=user_headers)).json()["data"]["board_frozen"]


async def test_hidden_results_and_cross_team_sessions_are_protected(client, admin_headers, user_headers):
    cid, uid, pid, submissions = await seed(client, admin_headers)
    path = f"/api/v1/contests/{cid}"
    await client.post(path + "/scoreboard-session", headers=admin_headers)
    assert (await client.get(path + "/scoreboard-session")).status_code == 401
    assert (await client.get(path + "/submissions", headers=user_headers)).status_code == 403
    assert (await client.get(path + f"/board/{uid}/{pid}/accepted", headers=user_headers)).status_code == 403
    # Contestants keep legitimate access to their own code/result.
    assert (await client.get(path + f"/submissions/{submissions[-1]}", headers=user_headers)).status_code == 200
    team = await client.post("/api/v1/teams", headers=admin_headers, json={"name": "Private resolver"})
    assert team.status_code == 200, team.text
    async with SessionLocal() as db:
        contest = await db.get(Contest, cid)
        contest.team_id = uuid.UUID(team.json()["data"]["id"])
        contest.contest_type = "team"
        await db.commit()
    assert (await client.get(path + "/scoreboard-session", headers=user_headers)).status_code == 403
    assert (await client.post(path + "/scoreboard-session", headers=user_headers)).status_code == 403
    assert (await client.get(path + "/scoreboard-session", headers=admin_headers)).status_code == 200


async def test_pending_judging_blocks_snapshot_and_late_pre_freeze_results_remain_public(client, admin_headers, user_headers):
    cid, uid, pid, submissions = await seed(client, admin_headers)
    path = f"/api/v1/contests/{cid}"
    async with SessionLocal() as db:
        late = await db.get(Submission, submissions[0])
        late.status = "judging"
        await db.commit()
    assert (await client.post(path + "/scoreboard-session", headers=admin_headers)).status_code == 409
    assert (await client.post(path + "/unfreeze", headers=admin_headers)).status_code == 409
    async with SessionLocal() as db:
        late = await db.get(Submission, submissions[0])
        late.status = "accepted"
        await db.flush()
        await ContestService(db).update_ranking_on_result(late, "accepted")
        await ContestService(db).update_ranking_on_result(late, "accepted")
        await db.commit()
    board = (await client.get(path + "/board", headers=user_headers)).json()["data"]
    cell = next(r for r in board["rows"] if r["user_id"] == str(uid))["cells"][0]
    assert cell["accepted"] and cell["penalty"] == 20 and cell["attempts"] == 0 and cell["pending"] == 0
    assert (await client.post(path + "/scoreboard-session", headers=admin_headers)).status_code == 200


async def test_pre_contest_board_columns_are_manager_only(client, admin_headers, user_headers):
    pid = await _seed_problem("Private future problem", visibility="private")
    payload = _contest_payload(problems=[{"problem_id": pid}], start_offset=3600, end_offset=7200)
    response = await client.post("/api/v1/contests", json=payload, headers=admin_headers)
    cid = response.json()["data"]["id"]
    path = f"/api/v1/contests/{cid}/board"
    hidden = await client.get(path, headers=user_headers)
    assert hidden.status_code == 200 and hidden.json()["data"]["problems"] == [] and hidden.json()["data"]["rows"] == []
    assert (await client.get(path, headers=admin_headers)).status_code == 200
