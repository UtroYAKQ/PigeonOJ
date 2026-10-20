"""Deterministic scoreboard arithmetic and replay projection (no I/O).

Submission order, never judge completion order, defines ACM penalties. The same
functions serve live/frozen boards, publication and immutable resolver snapshots.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.enums import RuleType, SubmissionStatus
from app.schemas.contest import BoardCell, BoardRow, RevealStep

UNSETTLED = {SubmissionStatus.PENDING, SubmissionStatus.JUDGING}
IGNORED = UNSETTLED | {SubmissionStatus.SYSTEM_ERROR}


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def submission_key(submission) -> tuple:
    return aware(submission.created_at), str(submission.id)


def row_key(rule_type: str, row: BoardRow) -> tuple:
    metric = (-row.solved, row.total_penalty) if rule_type == RuleType.ACM else (-row.total_score, -row.solved)
    return (*metric, row.nickname, str(row.user_id))


def rank_rows(rule_type: str, rows: list[BoardRow]) -> list[BoardRow]:
    for row in rows:
        recount(row)
    rows.sort(key=lambda row: row_key(rule_type, row))
    for index, row in enumerate(rows, 1):
        row.rank = index
        row.solved = sum(cell.accepted for cell in row.cells)
        row.total_penalty = sum(cell.penalty for cell in row.cells)
        row.total_score = sum(cell.score for cell in row.cells)
    return rows


def recount(row: BoardRow) -> None:
    row.solved = sum(cell.accepted for cell in row.cells)
    row.total_penalty = sum(cell.penalty for cell in row.cells)
    row.total_score = sum(cell.score for cell in row.cells)


def aggregate_rows(contest, subs: list, contest_problems: list, factor: int, nickname_of: dict) -> tuple[list[BoardRow], dict]:
    grouped: dict = {}
    problem_ids = {cp.problem_id for cp, _ in contest_problems}
    for submission in sorted(subs, key=submission_key):
        if submission.status in IGNORED or submission.problem_id not in problem_ids:
            continue
        if getattr(submission, "is_after_contest", False):
            continue
        grouped.setdefault((submission.user_id, submission.problem_id), []).append(submission)
    cells: dict = {}
    for key, group in grouped.items():
        first_ac = next((s for s in group if s.status == SubmissionStatus.ACCEPTED), None)
        before = group[:group.index(first_ac)] if first_ac is not None else group
        attempts = sum(s.status != SubmissionStatus.ACCEPTED for s in before)
        penalty = 0
        if first_ac is not None and contest.rule_type == RuleType.ACM:
            penalty = max(0, int((aware(first_ac.created_at) - aware(contest.start_time)).total_seconds() // 60)) + attempts * factor
        cells[key] = dict(
            accepted=first_ac is not None, accepted_at=first_ac.created_at if first_ac is not None else None,
            attempts=attempts, penalty=penalty,
            score=max((int(s.score or 0) for s in group), default=0) if contest.rule_type == RuleType.IOI else 0,
        )
    user_ids = set(nickname_of) | {uid for uid, _ in grouped}
    rows = []
    for uid in user_ids:
        row = BoardRow(
            rank=0, user_id=uid, nickname=nickname_of.get(uid, ""), solved=0, total_penalty=0, total_score=0,
            cells=[BoardCell(problem_id=cp.problem_id, letter=cp.letter, problem_score=cp.score,
                             **cells.get((uid, cp.problem_id), {})) for cp, _ in contest_problems],
        )
        recount(row)
        rows.append(row)
    return rank_rows(contest.rule_type, rows), cells


def mark_pending(rows: list[BoardRow], hidden: list, rule_type: str) -> None:
    counts = Counter((s.user_id, s.problem_id) for s in hidden if s.status != SubmissionStatus.SYSTEM_ERROR)
    for row in rows:
        for cell in row.cells:
            # An already public ACM AC cannot be changed by later submissions.
            cell.pending = 0 if rule_type == RuleType.ACM and cell.accepted else counts[(row.user_id, cell.problem_id)]
            cell.is_frozen = cell.pending > 0


def build_reveal_steps(rule_type: str, pending: list, final_rows: list[BoardRow], base_rows: list[BoardRow], nickname_of: dict) -> list[RevealStep]:
    """Resolve the CURRENT lowest unfinished row, then reorder and choose again.

    Final ranks are never used to select a contestant. Each step contains the
    complete resulting cell, making rewinds and skipped polling frames exact.
    """
    rows = [row.model_copy(deep=True) for row in base_rows]
    by_user = {row.user_id: row for row in rows}
    final = {(row.user_id, c.problem_id): c for row in final_rows for c in row.cells}
    queues: dict = {}
    public_ac = {(row.user_id, cell.problem_id) for row in base_rows for cell in row.cells if cell.accepted}
    for submission in sorted(pending, key=submission_key):
        if submission.status not in IGNORED and submission.user_id in by_user:
            if rule_type == RuleType.ACM and (submission.user_id, submission.problem_id) in public_ac:
                continue
            queues.setdefault(submission.user_id, []).append(submission)
    steps = []
    while queues:
        rank_rows(rule_type, rows)
        row = next(row for row in reversed(rows) if row.user_id in queues)
        queue = queues[row.user_id]
        submission = queue.pop(0)
        cell = next((c for c in row.cells if c.problem_id == submission.problem_id), None)
        if cell is not None:
            if not (rule_type == RuleType.ACM and cell.accepted):
                accepted = submission.status == SubmissionStatus.ACCEPTED
                if accepted and not cell.accepted:
                    cell.accepted = True
                    truth = final[(row.user_id, cell.problem_id)]
                    cell.penalty = truth.penalty
                    cell.accepted_at = truth.accepted_at
                elif not accepted and not cell.accepted:
                    cell.attempts += 1
                if rule_type == RuleType.IOI:
                    cell.score = max(cell.score, int(submission.score or 0))
            # Keep no-op post-AC steps: a shorter total would reveal an early
            # hidden AC before playback. Such submissions never alter scoring.
            cell.pending = 0 if rule_type == RuleType.ACM and cell.accepted else sum(s.problem_id == cell.problem_id for s in queue)
            cell.is_frozen = cell.pending > 0
            recount(row)
            steps.append(RevealStep(
                user_id=row.user_id, nickname=nickname_of.get(row.user_id, row.nickname),
                problem_id=cell.problem_id, letter=cell.letter, submission_id=submission.id,
                created_at=submission.created_at, accepted=cell.accepted,
                score=cell.score, penalty=cell.penalty, attempts=cell.attempts,
                cell=cell.model_copy(deep=True),
            ))
        if not queue:
            del queues[row.user_id]
    return steps


def project_rows(rule_type: str, base_rows: list[BoardRow], steps: list[RevealStep], cursor: int) -> list[BoardRow]:
    rows = [row.model_copy(deep=True) for row in base_rows]
    index = {(row.user_id, cell.problem_id): (row, i) for row in rows for i, cell in enumerate(row.cells)}
    for step in steps[:max(0, cursor)]:
        entry = index.get((step.user_id, step.problem_id))
        if entry and step.cell is not None:
            row, i = entry
            row.cells[i] = step.cell.model_copy(deep=True)
            recount(row)
    return rank_rows(rule_type, rows)
