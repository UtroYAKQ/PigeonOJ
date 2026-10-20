"""Arithmetic and server-clock tests run without PostgreSQL or Redis."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from app.schemas.contest import ScoreboardShowOut
from app.services.scoreboard import aggregate_rows, build_reveal_steps, mark_pending, project_rows
from app.services.scoreboard_session import ScoreboardSessionService, playback_cursor


@pytest.fixture(autouse=True)
def prepare_db():
    # Overrides the integration suite's destructive database fixture for pure tests.
    yield


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
UID = uuid.UUID(int=1)
PID = uuid.UUID(int=10)


def submission(n, minute, status, uid=UID, score=0):
    return NS(id=uuid.UUID(int=n), user_id=uid, problem_id=PID, created_at=START + timedelta(minutes=minute), status=status, score=score)


def snapshot(rule="ACM", subs=None, names=None):
    contest = NS(rule_type=rule, start_time=START)
    problems = [(NS(problem_id=PID, letter="A", score=100 if rule == "IOI" else 0), None)]
    subs = subs or []
    names = names or {UID: "A"}
    final, _ = aggregate_rows(contest, subs, problems, 20, names)
    base, _ = aggregate_rows(contest, [s for s in subs if s.created_at < START + timedelta(minutes=240)], problems, 20, names)
    hidden = [s for s in subs if s.created_at >= START + timedelta(minutes=240)]
    mark_pending(base, hidden, rule)
    steps = build_reveal_steps(rule, hidden, final, base, names)
    return base, final, steps


def test_submission_order_and_penalty_ignore_completion_and_post_ac_errors():
    subs = [submission(4, 18, "wrong_answer"), submission(3, 15, "accepted"), submission(2, 12, "wrong_answer"), submission(1, 10, "system_error")]
    _, rows, _ = snapshot(subs=subs)
    cell = rows[0].cells[0]
    assert (cell.attempts, cell.penalty, cell.accepted_at) == (1, 35, START + timedelta(minutes=15))


def test_equal_timestamp_uses_submission_id_and_stable_user_id():
    _, rows, _ = snapshot(subs=[submission(2, 12, "accepted"), submission(1, 12, "wrong_answer")], names={UID: "same", uuid.UUID(int=2): "same"})
    assert rows[0].total_penalty == 32
    assert rows[0].user_id == UID
    assert rows[1].solved == 0


@pytest.mark.parametrize("rule", ["ACM", "IOI"])
def test_replay_matches_final_and_keeps_only_frozen_contestants(rule):
    late = uuid.UUID(int=2)
    subs = [submission(1, 20, "wrong_answer", score=30), submission(2, 250, "wrong_answer", score=65), submission(3, 260, "accepted", score=100), submission(4, 270, "wrong_answer", score=35), submission(5, 265, "accepted", uid=late, score=100)]
    base, final, steps = snapshot(rule, subs, {UID: "A", late: "late", uuid.UUID(int=3): "zero"})
    assert len(base) == len(final) == 3
    assert sum(c.pending for row in base for c in row.cells) == 4
    assert project_rows(rule, base, steps, len(steps)) == final
    assert project_rows(rule, base, steps, 0) == base
    assert all(s.cell is not None for s in steps)


def test_public_ac_survives_freeze_and_repeated_ac_does_not_add_attempts():
    base, final, steps = snapshot(subs=[submission(1, 20, "accepted"), submission(2, 260, "wrong_answer"), submission(3, 270, "accepted")])
    assert base[0].cells[0].accepted and not base[0].cells[0].is_frozen
    assert not steps
    assert base == final


def test_total_steps_does_not_reveal_an_early_hidden_ac():
    _, _, early = snapshot(subs=[submission(1, 250, "accepted"), submission(2, 260, "wrong_answer")])
    _, _, late = snapshot(subs=[submission(1, 250, "wrong_answer"), submission(2, 260, "accepted")])
    assert len(early) == len(late) == 2
    assert early[-1].cell.attempts == 0


def test_selection_uses_current_bottom_instead_of_final_order():
    other = uuid.UUID(int=2)
    # B is currently last but finishes ahead of A: final-rank ordering would pick A.
    base, final, steps = snapshot(subs=[submission(1, 245, "wrong_answer"), submission(2, 250, "accepted", uid=other)], names={UID: "A", other: "B"})
    assert steps[0].user_id == other
    assert final[0].user_id == other
    assert project_rows("ACM", base, steps, len(steps)) == final


def test_server_playback_clock_projection_contains_no_future_data():
    base, final, steps = snapshot(subs=[submission(1, 250, "wrong_answer"), submission(2, 260, "accepted")])
    data = ScoreboardShowOut(contest_id=uuid.uuid4(), title="Test", rule_type="ACM", board_frozen=True, base_rows=base, final_rows=final, steps=steps)
    session = NS(id=uuid.uuid4(), snapshot=data.model_dump(mode="json"), cursor=0, playing=True, speed=1, anchor_at=START, revision=2)
    assert playback_cursor(session, len(steps), START + timedelta(seconds=1.79)) == 0
    first = ScoreboardSessionService.project(session, False, START + timedelta(seconds=1.8))
    assert first.cursor == 1 and not first.rows[0].cells[0].accepted
    payload = first.model_dump(mode="json")
    assert not {"snapshot", "final_rows", "steps"}.intersection(payload)
    end = ScoreboardSessionService.project(session, False, START + timedelta(days=1))
    assert end.rows == final and not end.playing
