"""比赛：建赛、报名、榜单、封榜。

契约见 docs/contracts/contests.md；涉及 contests / contest_problems /
contest_registrations / contest_rankings；封榜经 Celery 任务（contest_transition）推进。
提交与判题状态经 app.modules.judge.api 读取（单向依赖）。落地时对外能力经本包 api.py 暴露。
"""
