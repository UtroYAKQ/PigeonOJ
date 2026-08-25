from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.problem import Problem, TestCase as JudgeTestCase
from app.schemas.problem import TestCaseItem as JudgeTestCaseItem, TestCasesUpdate as JudgeTestCasesUpdate
from app.services.problem import ProblemService
from app.models.user import User


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
    monkeypatch.setattr("app.services.problem.get_storage", lambda: storage)
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        user = User(email=f"content-{uuid4()}@example.test", password="hash", nickname="owner", email_verified=True)
        db.add(user)
        await db.flush()
        problem = Problem(title="P", description="D", owner_id=user.id)
        db.add(problem)
        await db.flush()
        await db.commit()
        stale_keys = await ProblemService(db).replace_cases(user, problem.id, JudgeTestCasesUpdate(cases=[
            JudgeTestCaseItem(name="case1", input="1", expected_output="1"),
            JudgeTestCaseItem(name="hidden", input="2", expected_output="4"),
        ]))
        await db.commit()
        # 全部 cases 均为正式测试点：input/output 各上传一份
        assert len(storage.puts) == 4
        rows = list((await db.scalars(select(JudgeTestCase).where(JudgeTestCase.problem_id == problem.id))).all())
        assert all(row.input_oss_id and row.expected_output_oss_id for row in rows)
        assert rows[0].input_oss_id.startswith(f"problems/{problem.id}/cases/")
        # 返回被替换对象 key 供事务提交后异步清理（首次替换为空）
        assert stale_keys == []

        # 二次全量替换：旧对象进入待清理列表
        stale_keys = await ProblemService(db).replace_cases(user, problem.id, JudgeTestCasesUpdate(cases=[
            JudgeTestCaseItem(name="case2", input="5", expected_output="5"),
        ]))
        assert len(stale_keys) == 4
