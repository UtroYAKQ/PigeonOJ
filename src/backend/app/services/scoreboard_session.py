"""Shared playback uses a durable server clock; no browser owns the timer."""
import uuid
from datetime import datetime, timezone

from app.core.exceptions import APIError, RESOURCE_NOT_FOUND, RESOURCE_STATE_CONFLICT
from app.repositories.scoreboard import ScoreboardSessionRepository
from app.schemas.contest import BoardProblemOut, ScoreboardCommand, ScoreboardSessionOut, ScoreboardShowOut
from app.services.contest import ContestService
from app.services.scoreboard import aware, project_rows


def playback_cursor(session, total: int, now: datetime) -> int:
    elapsed = 0
    if session.playing and session.anchor_at is not None:
        elapsed = max(0, int((aware(now) - aware(session.anchor_at)).total_seconds() * session.speed / 1.8))
    return min(total, session.cursor + elapsed)


class ScoreboardSessionService:
    def __init__(self, db, contests: ContestService):
        self.db = db
        self.contests = contests
        self.repo = ScoreboardSessionRepository(db)

    async def create(self, user, contest_id):
        await self.contests.require_manage(contest_id, user)
        await self.repo.lock_contest(contest_id)
        session = await self.repo.get(contest_id)
        if session is None:
            snapshot = await self.contests.scoreboard_show(user, contest_id)
            session = await self.repo.create(contest_id, snapshot.model_dump(mode="json"))
        return self.project(session, True)

    async def get(self, user, contest_id):
        contest = await self.contests._get_contest(contest_id)
        await self.contests._ensure_team_view(contest, user)
        session = await self.repo.get(contest_id)
        if session is None:
            raise APIError(RESOURCE_NOT_FOUND, "滚榜会话尚未创建", 404)
        return self.project(session, await self.contests._can_manage(user, contest))

    async def command(self, user, contest_id, body: ScoreboardCommand):
        await self.contests.require_manage(contest_id, user)
        session = await self.repo.get(contest_id, lock=True)
        if session is None:
            raise APIError(RESOURCE_NOT_FOUND, "滚榜会话尚未创建", 404)
        if session.last_command_id == body.command_id:
            return self.project(session, True)
        if session.revision != body.revision:
            raise APIError(RESOURCE_STATE_CONFLICT, "滚榜进度已变化，请刷新后重试", 409)
        now = datetime.now(timezone.utc)
        if body.action == "prepare":
            snapshot = await self.contests.scoreboard_show(user, contest_id)
            session.snapshot = snapshot.model_dump(mode="json")
            session.id = uuid.uuid4()
            session.cursor = 0
            session.playing = False
            session.anchor_at = None
        total = len(session.snapshot["steps"])
        cursor = playback_cursor(session, total, now)
        if body.action == "next":
            cursor = min(total, cursor + 1)
        elif body.action == "previous":
            cursor = max(0, cursor - 1)
        elif body.action == "restart":
            cursor = 0
        if body.action == "speed":
            session.speed = body.speed
        elif body.action == "play":
            session.playing = cursor < total
        else:
            session.playing = False
        session.cursor = cursor
        session.playing = session.playing and cursor < total
        session.anchor_at = now if session.playing else None
        session.revision += 1
        session.last_command_id = body.command_id
        await self.db.flush()
        return self.project(session, True, now)

    @staticmethod
    def project(session, can_control: bool, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        data = ScoreboardShowOut.model_validate(session.snapshot)
        cursor = playback_cursor(session, len(data.steps), now)
        return ScoreboardSessionOut(
            id=session.id, contest_id=data.contest_id, title=data.title, rule_type=data.rule_type,
            board_frozen=data.board_frozen, revision=session.revision, cursor=cursor,
            total_steps=len(data.steps), playing=session.playing and cursor < len(data.steps), speed=session.speed,
            server_time=now, can_control=can_control,
            problems=[BoardProblemOut.model_validate(p, from_attributes=True) for p in data.problems],
            rows=project_rows(data.rule_type, data.base_rows, data.steps, cursor),
            current_step=data.steps[cursor - 1] if cursor else None,
        )
