"""比赛：建赛、报名、榜单、封榜。

契约见 docs/contracts/contests.md；涉及 contests / contest_problems /
contest_registrations / contest_rankings；封榜经 Celery 任务（contest_transition）。
"""
