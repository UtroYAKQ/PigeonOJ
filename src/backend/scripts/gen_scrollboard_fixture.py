"""生成滚榜大屏（public/scrollboard.html）的真实形状数据包 fixture。

目的：前端页面（独立静态页）平时只能用 `?mock=1` 的内置演示数据自测，那份数据是前端自己
照着契约复刻的 —— 一旦后端 `RevealStep` / `BoardCell` 字段口径变了，mock 仍会「自洽通过」，
真实数据却会炸。本脚本直接调用后端**真实的** `build_reveal_steps` 纯函数生成 `steps`，
再经 `ScoreboardShowOut` 序列化，产出的 JSON 与线上端点返回逐字段一致。

**不连接数据库、不写任何表**：base_rows / final_rows 在内存里构造，pending 提交用
duck-typing 的轻量对象（`build_reveal_steps` 只读 created_at / problem_id / status /
score / user_id / id 六个属性）。

用法：
    python scripts/gen_scrollboard_fixture.py --out /tmp/scoreboard-show.json
    python scripts/gen_scrollboard_fixture.py --rule IOI --teams 14 --problems 6
    python scripts/gen_scrollboard_fixture.py --teams 0 --problems 3   # 空边界

配合前端冒烟（校验页面能否吃下真实端点输出）：
    node scripts/check-scrollboard.mjs --fixture=<上面的 json 路径>
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.enums import RuleType, SubmissionStatus  # noqa: E402
from app.schemas.contest import (  # noqa: E402
    BoardCell,
    BoardRow,
    ContestProblemItemOut,
    ScoreboardShowOut,
)
from app.services.contest import _row_key, build_reveal_steps  # noqa: E402

DURATION_MIN = 300   # 比赛总时长（分钟）
FREEZE_MIN = 240     # 封榜时刻
FULL_SCORE = 100     # 单题满分
FACTOR = 20          # ACM 每次错误提交的罚时（分钟）

NAME_POOL = [
    "晨曦战队", "NightOwl", "键盘侠联盟", "递归深处", "ZeroError", "月见黑",
    "堆栈猎人", "编译通过", "lazy_cat", "三分钟热度", "摸鱼选手", "CtrlCV 大师",
    "算法苦手", "紫金落日", "HelloWorld", "二分天下", "并查集爱好者", "TLE 制造机",
    "图上观星", "动态规划学徒", "贪心就好", "暴力出奇迹", "常数优化家", "打表过题王",
    "内存超限", "指针漂移", "快排了解一下", "背包九讲", "最短路旅客", "拓扑排序中",
]


@dataclass
class FakeSubmission:
    """duck-typing 的提交对象：build_reveal_steps 只读取下列属性。"""

    id: uuid.UUID
    user_id: uuid.UUID
    problem_id: uuid.UUID
    created_at: datetime
    status: SubmissionStatus
    score: int = 0


@dataclass
class CellState:
    accepted: bool = False
    attempts: int = 0          # 错误提交次数
    penalty: int = 0           # ACM：该格罚时（分钟）
    score: int = 0             # IOI：该格最高分
    accepted_at: datetime | None = field(default=None)


def _uuid(rnd: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rnd.getrandbits(128), version=4)


def _rows_from(cell_state: dict[uuid.UUID, dict[uuid.UUID, CellState]],
               problems: list[ContestProblemItemOut],
               problems_by_id: dict[uuid.UUID, ContestProblemItemOut],
               nick_of: dict[uuid.UUID, str],
               rule_type: str) -> list[BoardRow]:
    """按后端 _row_key 口径排序并写入 rank。"""
    rows: list[BoardRow] = []
    for uid, by_pid in cell_state.items():
        cells = []
        for p in problems:
            c = by_pid[p.problem_id]
            cells.append(BoardCell(
                problem_id=p.problem_id,
                letter=p.letter,
                problem_score=p.score,
                accepted=c.accepted,
                attempts=c.attempts,
                penalty=c.penalty,
                score=c.score,
                is_frozen=False,
                accepted_at=c.accepted_at,
            ))
        rows.append(BoardRow(
            rank=0,
            user_id=uid,
            nickname=nick_of[uid],
            solved=sum(1 for c in cells if c.accepted),
            total_penalty=sum(c.penalty for c in cells),
            total_score=sum(c.score for c in cells),
            cells=cells,
        ))
    rows.sort(key=lambda r: _row_key(rule_type, r))
    for i, r in enumerate(rows):
        r.rank = i + 1
    return rows


def generate(*, rule_type: str, teams: int, problems_n: int, seed: int,
             empty: bool = False) -> dict:
    rnd = random.Random(seed)
    acm = rule_type == RuleType.ACM.value

    problems = [
        ContestProblemItemOut(
            problem_id=_uuid(rnd),
            letter=chr(ord("A") + j),
            score=FULL_SCORE,
            sort_order=j,
            title=f"题目 {chr(ord('A') + j)}",
            difficulty=1 + round(j / max(1, problems_n - 1) * 4),
        )
        for j in range(problems_n)
    ]
    problems_by_id = {p.problem_id: p for p in problems}

    team_ids = [_uuid(rnd) for _ in range(teams)]
    nick_of = {
        uid: NAME_POOL[i % len(NAME_POOL)] + (f" {i // len(NAME_POOL) + 1}" if i >= len(NAME_POOL) else "")
        for i, uid in enumerate(team_ids)
    }
    strength = {
        uid: max(0.05, min(0.99, 0.92 - 0.62 * (i / max(1, teams - 1)) + (rnd.random() - 0.5) * 0.18))
        for i, uid in enumerate(team_ids)
    }

    start = datetime.now(timezone.utc) - timedelta(minutes=DURATION_MIN)
    base: dict[uuid.UUID, dict[uuid.UUID, CellState]] = {}
    pending: list[FakeSubmission] = []

    for uid in team_ids:
        by_pid = {p.problem_id: CellState() for p in problems}
        for j, p in enumerate(problems):
            rel = j / max(1, problems_n - 1)
            cur = by_pid[p.problem_id]
            p_solve = max(0.03, min(0.96, strength[uid] * 0.98 - rel * 0.6 + (rnd.random() - 0.5) * 0.16))
            if rnd.random() < p_solve:
                wrong = 1 + int(rnd.random() * 2) if rnd.random() < 0.45 else 0
                ac_min = 20 + rel * 130 + rnd.random() * 70
                cur.accepted = True
                cur.attempts = wrong
                cur.penalty = round(ac_min) + wrong * FACTOR
                cur.score = FULL_SCORE
                cur.accepted_at = start + timedelta(minutes=ac_min)
            else:
                cur.attempts = int(rnd.random() * 3) if rnd.random() < 0.55 else 0
                if not acm and rnd.random() < 0.4:
                    cur.score = int(rnd.random() * 60) + 10
        base[uid] = by_pid

        if empty:
            continue
        # 封榜期提交：0~3 条，优先打没过的题
        for _ in range(1 + int(rnd.random() * 3) if rnd.random() < 0.78 else 0):
            unsolved = [p for p in problems if not by_pid[p.problem_id].accepted]
            pool = unsolved if (unsolved and rnd.random() < 0.85) else problems
            p = pool[int(rnd.random() * len(pool))]
            cur = by_pid[p.problem_id]
            at_min = FREEZE_MIN + 2 + rnd.random() * (DURATION_MIN - FREEZE_MIN - 4)
            rel = problems.index(p) / max(1, problems_n - 1)
            ok = rnd.random() < max(0.08, min(0.85, strength[uid] * 0.75 - rel * 0.28))
            score = FULL_SCORE if ok else (int(rnd.random() * 70) + 10 if not acm else 0)
            pending.append(FakeSubmission(
                id=_uuid(rnd),
                user_id=uid,
                problem_id=p.problem_id,
                created_at=start + timedelta(minutes=at_min),
                status=SubmissionStatus.ACCEPTED if ok else SubmissionStatus.WRONG_ANSWER,
                score=score,
            ))

    # 终局态 = 封榜快照 + 全部封榜期提交（按提交时间序）
    final: dict[uuid.UUID, dict[uuid.UUID, CellState]] = {
        uid: {pid: CellState(**vars(c)) for pid, c in by_pid.items()}
        for uid, by_pid in base.items()
    }
    for s in sorted(pending, key=lambda s: s.created_at):
        c = final[s.user_id][s.problem_id]
        if s.status == SubmissionStatus.ACCEPTED:
            if not c.accepted:
                c.accepted = True
                c.penalty = int((s.created_at - start).total_seconds() // 60) + c.attempts * FACTOR
                c.accepted_at = s.created_at
            c.score = FULL_SCORE
        else:
            c.attempts += 1
            c.score = max(c.score, int(s.score or 0))

    base_rows = _rows_from(base, problems, problems_by_id, nick_of, rule_type)
    final_rows = _rows_from(final, problems, problems_by_id, nick_of, rule_type)
    steps = build_reveal_steps(rule_type, pending, final_rows, base_rows, nick_of)

    out = ScoreboardShowOut(
        contest_id=_uuid(rnd),
        title=f"{rule_type} 真实形状夹具 · seed {seed}",
        rule_type=RuleType(rule_type),
        board_frozen=True,
        frozen_at=start + timedelta(minutes=FREEZE_MIN),
        problems=problems,
        base_rows=base_rows,
        final_rows=final_rows,
        steps=steps,
    )
    # pydantic v2 的 model_dump(mode="json") 直接给出 JSON 原生类型（UUID/datetime 已转成 str）
    return out.model_dump(mode="json")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成滚榜大屏 fixture（不连库）")
    ap.add_argument("--rule", choices=["ACM", "IOI"], default="ACM")
    ap.add_argument("--teams", type=int, default=18)
    ap.add_argument("--problems", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--empty", action="store_true", help="不生成封榜期提交（steps 为空的边界）")
    ap.add_argument("--out", default="-", help="输出路径，- 表示 stdout")
    args = ap.parse_args()

    payload = generate(
        rule_type=args.rule,
        teams=args.teams,
        problems_n=args.problems,
        seed=args.seed,
        empty=args.empty,
    )
    text = json.dumps(payload, ensure_ascii=False)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写出 {args.out}：{len(payload['base_rows'])} 队 / "
              f"{len(payload['problems'])} 题 / {len(payload['steps'])} 步", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
