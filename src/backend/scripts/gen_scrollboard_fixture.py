"""Generate deterministic, real-schema resolver fixtures without a database."""
from __future__ import annotations
import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.contest import ContestProblemItemOut, ScoreboardShowOut
from app.services.scoreboard import aggregate_rows, build_reveal_steps, mark_pending


def generate(rule_type="ACM", teams=18, problems_n=8, seed=20260903, empty=False):
    rnd = random.Random(seed)
    new_id = lambda: uuid.UUID(int=rnd.getrandbits(128), version=4)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    contest = NS(start_time=start, rule_type=rule_type)
    problems = [NS(problem_id=new_id(), letter=chr(65 + i), score=100 if rule_type == "IOI" else 0, sort_order=i, title=f"Problem {i+1}") for i in range(problems_n)]
    names = {new_id(): f"队伍 Team {i+1:02d}" for i in range(teams)}
    subs = []
    for index, uid in enumerate(names):
        for problem in problems:
            # Some users first submit after the freeze; some never submit.
            if index % 7 == 0:
                continue
            for attempt in range(rnd.randrange(5)):
                minute = rnd.randrange(5, 300)
                if index % 5 == 0:
                    minute = rnd.randrange(240, 300)
                if empty and minute >= 240:
                    continue
                accepted = rnd.random() < .35
                subs.append(NS(id=new_id(), user_id=uid, problem_id=problem.problem_id,
                    created_at=start + timedelta(minutes=minute, seconds=attempt),
                    status="accepted" if accepted else "wrong_answer",
                    score=100 if accepted else rnd.randrange(80) if rule_type == "IOI" else 0))
    pairs = [(p, None) for p in problems]
    final, _ = aggregate_rows(contest, subs, pairs, 20, names)
    visible = [s for s in subs if s.created_at < start + timedelta(minutes=240)]
    hidden = [s for s in subs if s not in visible]
    base, _ = aggregate_rows(contest, visible, pairs, 20, names)
    mark_pending(base, hidden, rule_type)
    steps = build_reveal_steps(rule_type, hidden, final, base, names)
    return ScoreboardShowOut(contest_id=new_id(), title=f"PigeonOJ {rule_type} · {seed}", rule_type=rule_type,
        board_frozen=True, frozen_at=start+timedelta(minutes=240),
        problems=[ContestProblemItemOut(**vars(p)) for p in problems],
        base_rows=base, final_rows=final, steps=steps).model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", choices=["ACM", "IOI"], default="ACM")
    parser.add_argument("--teams", type=int, default=18)
    parser.add_argument("--problems", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260903)
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--out", default="-")
    args = parser.parse_args()
    if not 0 <= args.teams <= 1000 or not 0 <= args.problems <= 26:
        parser.error("teams must be 0..1000, problems must be 0..26")
    payload = generate(args.rule, args.teams, args.problems, args.seed, args.empty)
    text = json.dumps(payload, ensure_ascii=False)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{args.out}: {len(payload['base_rows'])} rows, {len(payload['steps'])} steps")


if __name__ == "__main__":
    main()
