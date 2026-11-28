"""依赖装配图测试：Provider 工厂构造与 dependency_overrides 可替换性。

覆盖 docs/architecture.md 依赖注入约定：
- deps.py 的 Provider 在构造期装配协作者（Service / Protocol 端口），同一请求共享 db 会话；
- 路由通过 Annotated Provider 拿到的实现可被 app.dependency_overrides 整体替换。
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import (
    ProblemServiceDep,
    get_auth_service,
    get_config_service,
    get_contest_service,
    get_dispatcher,
    get_org_service,
    get_problem_service,
    get_problem_set_service,
    get_self_test_service,
    get_submission_service,
    get_team_admin_service,
    get_team_service,
    get_team_space_service,
    get_user_service,
)
from app.core.database import SessionLocal

pytestmark = pytest.mark.no_db


async def test_provider_factories_wire_collaborators_on_shared_session() -> None:
    """Provider 图：协作者与端口均为构造注入，且共享同一个 AsyncSession。"""
    db = SessionLocal()
    try:
        config = get_config_service(db)
        users = get_user_service(db)
        auth = get_auth_service(db, users, config)
        problems = get_problem_service(db)
        dispatcher = get_dispatcher(db)
        submissions = get_submission_service(db, problems, dispatcher)
        teams = get_team_service(db, config)
        problem_sets = get_problem_set_service(db, problems, teams, submissions, dispatcher)
        contests = get_contest_service(db, config, submissions, problems, teams, dispatcher)
        self_test = get_self_test_service(db, config)
        space = get_team_space_service(
            db, teams, problems, problem_sets, contests, submissions, self_test, dispatcher
        )
        org = get_org_service(db, problems)
        admin = get_team_admin_service(teams, space)

        assert problems.db is db
        assert auth.config is config
        assert auth._user_view is users
        assert self_test.config_service is config

        assert submissions._verification is problems
        assert submissions._dispatcher is dispatcher

        assert contests._submitter is submissions
        assert contests._dispatcher is dispatcher
        assert contests._problem_detail is problems
        assert contests._submission_detail is submissions
        assert contests._team_roles is teams
        assert contests.config is config

        assert problem_sets._problem_detail is problems
        assert problem_sets._team_roles is teams
        assert problem_sets._submission_creator is submissions
        assert problem_sets._dispatcher is dispatcher

        assert space.problem_sets is problem_sets
        assert space._self_test is self_test
        assert space._dispatcher is dispatcher

        assert org._problems is problems
        assert admin.teams is teams
        assert admin.space is space
    finally:
        await db.close()


async def test_router_provider_is_replaceable_via_dependency_overrides() -> None:
    """Provider 图整体可替换：覆盖 get_problem_service 后路由拿到替身（不解析 db 依赖）。"""
    probe_app = FastAPI()

    @probe_app.get("/probe")
    async def probe(service: ProblemServiceDep):
        return {"marker": getattr(service, "marker", None)}

    probe_app.dependency_overrides[get_problem_service] = lambda: SimpleNamespace(marker="stub")
    transport = httpx.ASGITransport(app=probe_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"marker": "stub"}