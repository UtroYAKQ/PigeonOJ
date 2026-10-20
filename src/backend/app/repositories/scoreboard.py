"""Resolver session persistence. Authorization and playback policy live in services."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import Contest, ScoreboardSession


class ScoreboardSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def lock_contest(self, contest_id: uuid.UUID) -> None:
        # Serializes creation with another controller and contest state changes.
        await self.db.execute(select(Contest).where(Contest.id == contest_id).with_for_update().execution_options(populate_existing=True))

    async def get(self, contest_id: uuid.UUID, *, lock: bool = False) -> ScoreboardSession | None:
        query = select(ScoreboardSession).where(ScoreboardSession.contest_id == contest_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.db.scalar(query)

    async def create(self, contest_id: uuid.UUID, snapshot: dict) -> ScoreboardSession:
        session = ScoreboardSession(contest_id=contest_id, snapshot=snapshot, revision=0, cursor=0, playing=False, speed=1)
        self.db.add(session)
        await self.db.flush()
        return session
