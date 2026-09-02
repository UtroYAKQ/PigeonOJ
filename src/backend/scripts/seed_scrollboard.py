"""滚榜测试数据种子脚本（一次性，幂等可重跑）。

向开发库塞一场已结束且处于封榜状态的 ACM 比赛「滚榜测试赛」：
- 5 支队伍、3 道题（A/B/C）
- 封榜快照 = 封榜前的真实结果（榜单行 is_frozen=true）
- 封榜期提交只落 submissions（Delta 从垫底翻盘到第 2、Echo 上分等戏剧性场景）
- 揭晓顺序（最终名次从差到好）：Echo → Charlie → Delta → Alpha

用法：python scripts/seed_scrollboard.py
⚠️ 写入 DATABASE_URL 指向的开发库；请勿指向生产库。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.enums import SubmitType
from app.models.contest import Contest, ContestProblem, ContestRanking, ContestRegistration
from app.models.judge import Submission
from app.models.problem import Problem
from app.models.user import User

CONTEST_TITLE = "滚榜测试赛"
FACTOR = 20  # ACM 罚时系数（分钟）


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _get_or_create_user(db, email: str, nickname: str) -> User:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        # password 列存 bcrypt 哈希；种子账号不用于登录，占位值即可
        user = User(email=email, nickname=nickname, password="!", email_verified=True)
        db.add(user)
        await db.flush()
    return user


async def main() -> None:
    async with SessionLocal() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@pigeonoj.dev"))
        ).scalar_one()

        # ---- 幂等清理：删掉旧种子赛 ----
        old = (
            await db.execute(select(Contest).where(Contest.title == CONTEST_TITLE))
        ).scalar_one_or_none()
        if old is not None:
            await db.execute(delete(Submission).where(Submission.contest_id == old.id))
            await db.execute(delete(ContestRanking).where(ContestRanking.contest_id == old.id))
            await db.execute(delete(ContestProblem).where(ContestProblem.contest_id == old.id))
            await db.execute(
                delete(ContestRegistration).where(ContestRegistration.contest_id == old.id)
            )
            await db.delete(old)
            await db.flush()

        # ---- 队伍（用户） ----
        teams = {}
        for code, nickname in [
            ("alpha", "队伍 Alpha"),
            ("bravo", "队伍 Bravo"),
            ("charlie", "队伍 Charlie"),
            ("delta", "队伍 Delta"),
            ("echo", "队伍 Echo"),
        ]:
            teams[code] = await _get_or_create_user(
                db, f"scroll-{code}@pigeonoj.dev", nickname
            )

        # ---- 题目 A / B / C ----
        problems = {}
        for letter, title in [("A", "滚榜题 A"), ("B", "滚榜题 B"), ("C", "滚榜题 C")]:
            problem = (
                await db.execute(select(Problem).where(Problem.title == title))
            ).scalar_one_or_none()
            if problem is None:
                problem = Problem(
                    title=title, description="滚榜测试题目", owner_id=admin.id,
                    status="published", visibility="public",
                    verified_at=datetime.now(timezone.utc),
                )
                db.add(problem)
                await db.flush()
            problems[letter] = problem

        # ---- 比赛：已结束 + 封榜中 ----
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=2)
        end = now - timedelta(minutes=5)
        freeze_at = end - timedelta(seconds=300)  # 结束前 5 分钟封榜

        contest = Contest(
            title=CONTEST_TITLE,
            description="滚榜功能测试数据（自动封榜 → 赛后人工解榜前的大屏回放）",
            contest_type="public",
            owner_id=admin.id,
            rule_type="ACM",
            start_time=start,
            end_time=end,
            register_start_time=start - timedelta(hours=1),
            register_end_time=freeze_at,
            freeze_time=freeze_at,
            board_frozen=True,
            frozen_at=freeze_at,
            status="finished",
        )
        db.add(contest)
        await db.flush()

        for problem, letter, sort_order in [
            (problems["A"], "A", 1),
            (problems["B"], "B", 2),
            (problems["C"], "C", 3),
        ]:
            db.add(
                ContestProblem(
                    contest_id=contest.id, problem_id=problem.id,
                    letter=letter, sort_order=sort_order, score=100,
                )
            )
            await db.flush()
        for user in teams.values():
            db.add(ContestRegistration(contest_id=contest.id, user_id=user.id))
        await db.flush()

        # ---- 提交与封榜前榜单 ----
        # 提交时间基准：start 后按分钟分布；封榜期提交 created_at >= freeze_at
        def t(minutes: int) -> datetime:
            return start + timedelta(minutes=minutes)

        # (队伍, 题, 提交分钟, 状态)  — 封榜线 = 第 115 分钟（end-5min）
        pre_freeze = [
            ("alpha", "A", 20, "accepted"),
            ("alpha", "B", 55, "accepted"),
            ("bravo", "A", 70, "accepted"),
            ("charlie", "A", 40, "accepted"),
            ("charlie", "C", 80, "wrong_answer"),
            ("charlie", "C", 95, "wrong_answer"),
            ("echo", "A", 90, "wrong_answer"),
        ]
        in_freeze = [
            ("delta", "A", 118, "accepted"),    # 翻盘：0 → 2 题
            ("delta", "B", 119, "accepted"),
            ("charlie", "C", 117, "accepted"),  # 1 → 2 题
            ("echo", "A", 116, "accepted"),     # 0 → 1 题
            ("alpha", "C", 118, "wrong_answer"),
            ("alpha", "C", 119, "accepted"),    # 2 → 3 题
        ]

        attempt_counter: dict[tuple, int] = {}

        async def add_sub(uid, pid, created: datetime, status: str) -> Submission:
            key = (uid, pid)
            attempt_counter[key] = attempt_counter.get(key, 0) + (0 if status == "accepted" else 1)
            sub = Submission(
                user_id=uid, problem_id=pid, language="cpp17", code="/* scroll */",
                submit_type=SubmitType.CONTEST, contest_id=contest.id,
                status=status, score=100 if status == "accepted" else 0,
                created_at=created,
            )
            db.add(sub)
            await db.flush()
            return sub

        def penalty_of(created: datetime, attempts: int) -> int:
            return int((created - start).total_seconds() // 60) + attempts * FACTOR

        # 封榜前：提交 + 榜单行（快照来源）
        pre_rows: list[tuple] = []
        for code, letter, minute, status in pre_freeze:
            uid, pid = teams[code].id, problems[letter].id
            created = t(minute)
            sub = await add_sub(uid, pid, created, status)
            key = (uid, pid)
            row = next((r for r in pre_rows if r[0] == uid and r[1] == pid), None)
            if status == "accepted" and row is None:
                attempts = sum(
                    1 for c, _l, m, st in pre_freeze
                    if c == code and st != "accepted" and m < minute
                )
                pre_rows.append(
                    (uid, pid, True, created, attempts, penalty_of(created, attempts))
                )
            elif status != "accepted":
                # 错误提交：已有未 AC 行则累积 attempts；否则新建行（对齐 ensure_row 语义）
                if row is not None:
                    pre_rows = [r for r in pre_rows if not (r[0] == uid and r[1] == pid)]
                pre_rows.append((uid, pid, False, None, attempt_counter[key], 0))

        # 封榜期：只落 submissions（不写榜单行 = 冻结不可见）
        for code, letter, minute, status in in_freeze:
            uid, pid = teams[code].id, problems[letter].id
            await add_sub(uid, pid, t(minute), status)

        # 榜单行（is_frozen=true，封榜后不再更新）
        for uid, pid, accepted, accepted_at, attempts, penalty in pre_rows:
            db.add(
                ContestRanking(
                    contest_id=contest.id, user_id=uid, problem_id=pid,
                    accepted=accepted, accepted_at=accepted_at,
                    attempts=attempts, penalty=penalty,
                    score=0, is_frozen=True,
                )
            )

        await db.commit()
        print(f"种子完成：contest_id={contest.id}")
        print(f"  封榜线 {freeze_at.isoformat()} | 快照队伍 {len(pre_rows)} 格")
        print("  打开 /admin/contests → 该比赛行「赛时工具」→ 滚榜大屏")


if __name__ == "__main__":
    asyncio.run(main())
