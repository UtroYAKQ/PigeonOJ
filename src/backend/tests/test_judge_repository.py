from __future__ import annotations

import pytest

from app.modules.judge.models import Problem, Submission, TestCase as JudgeTestCase
from app.modules.judge.repository import JudgeRepository
from app.modules.users.models import User


@pytest.mark.asyncio
async def test_repository_loads_only_non_sample_cases():
    from app.shared.database import SessionLocal

    async with SessionLocal() as db:
        user = User(email="judge-owner@example.test", password="hash", nickname="owner", email_verified=True)
        db.add(user)
        await db.flush()
        problem = Problem(title="P", description="D", owner_id=user.id)
        db.add(problem)
        await db.flush()
        db.add_all([
            JudgeTestCase(problem_id=problem.id, is_sample=True, sample_input="1", sample_output="1", sort_order=0),
            JudgeTestCase(problem_id=problem.id, input_oss_id="in", expected_output_oss_id="out", score=100, sort_order=1),
        ])
        submission = Submission(user_id=user.id, problem_id=problem.id, language="python3.12", code="print(1)")
        db.add(submission)
        await db.commit()
        bundle = await JudgeRepository().get_bundle(db, submission.id)
        assert bundle is not None
        assert len(bundle.test_cases) == 1
        assert bundle.test_cases[0].input_oss_id == "in"
