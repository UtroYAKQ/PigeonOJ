from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.judge.models import Problem, TestCase as JudgeTestCase
from app.modules.judge.schemas import TestCaseItem as JudgeTestCaseItem, TestCasesUpdate as JudgeTestCasesUpdate
from app.modules.judge.service import ProblemService
from app.modules.users.models import User


@pytest.mark.asyncio
async def test_replace_cases_uploads_only_official_content(monkeypatch):
    class FakeStorage:
        def __init__(self):
            self.puts = []
            self.deletes = []

        async def put_bytes(self, key, content, content_type):
            self.puts.append((key, content, content_type))

        async def delete(self, key):
            self.deletes.append(key)

    storage = FakeStorage()
    monkeypatch.setattr("app.modules.judge.service.get_storage", lambda: storage)
    from app.shared.database import SessionLocal

    async with SessionLocal() as db:
        user = User(email=f"content-{uuid4()}@example.test", password="hash", nickname="owner", email_verified=True)
        db.add(user)
        await db.flush()
        problem = Problem(title="P", description="D", owner_id=user.id)
        db.add(problem)
        await db.flush()
        await db.commit()
        await ProblemService(db).replace_cases(user, problem.id, JudgeTestCasesUpdate(cases=[
            JudgeTestCaseItem(name="sample", is_sample=True, input="1", expected_output="1"),
            JudgeTestCaseItem(name="hidden", input="2", expected_output="4", score=100),
        ]))
        await db.commit()
        assert len(storage.puts) == 2
        rows = list((await db.scalars(select(JudgeTestCase).where(JudgeTestCase.problem_id == problem.id))).all())
        assert rows[0].sample_input == "1"
        assert rows[0].input_oss_id is None
        assert rows[1].input_oss_id.startswith(f"problems/{problem.id}/cases/")
