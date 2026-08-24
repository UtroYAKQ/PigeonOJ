# 比赛模块契约

> 公开 / 团队比赛、报名、实时榜单与封榜。计分按 `rule_type` 区分 ACM / IOI。

## 数据模型

### `contests` — 比赛表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(128) | NOT NULL | 比赛名称 |
| description | TEXT | NULL | 比赛说明 |
| contest_type | VARCHAR(16) | NOT NULL | `public` 公开比赛 / `team` 团队比赛 |
| team_id | UUID | NULL, FK → teams.id | 团队比赛所属团队 |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者 |
| rule_type | VARCHAR(8) | NOT NULL | `ACM` / `IOI` |
| start_time | TIMESTAMPTZ | NOT NULL | 开始时间 |
| end_time | TIMESTAMPTZ | NOT NULL | 结束时间 |
| register_start_time | TIMESTAMPTZ | NOT NULL | 报名开始时间 |
| register_end_time | TIMESTAMPTZ | NOT NULL | 报名截止时间 |
| freeze_offset_seconds | INT | NOT NULL DEFAULT 0 | 封榜时间 = 结束前 N 秒 |
| board_frozen | BOOLEAN | NOT NULL DEFAULT false | 当前是否处于封榜中 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'scheduled' | `scheduled` / `running` / `finished` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK 约束：

```sql
CHECK (register_end_time <= end_time)   -- 报名截止不晚于比赛结束
```

索引：INDEX(`status`, `start_time`)、INDEX(`team_id`, `contest_type`)

### `contest_problems` — 比赛题目关联表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| contest_id | UUID | NOT NULL, FK → contests.id | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| letter | VARCHAR(4) | NULL | 题目编号（A/B/C…） |
| sort_order | INT | NOT NULL DEFAULT 0 | |
| score | INT | NOT NULL DEFAULT 0 | IOI 单题分值 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`contest_id`, `problem_id`)、INDEX(`problem_id`)

### `contest_registrations` — 比赛报名表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| contest_id | UUID | NOT NULL, FK → contests.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| status | VARCHAR(16) | NOT NULL DEFAULT 'registered' | `registered` / `cancelled` |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`contest_id`, `user_id`)、INDEX(`user_id`)

### `contest_rankings` — 比赛榜单记录表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| contest_id | UUID | NOT NULL, FK → contests.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| accepted | BOOLEAN | NOT NULL DEFAULT false | 是否通过 |
| accepted_at | TIMESTAMPTZ | NULL | 首次通过时间 |
| attempts | INT | NOT NULL DEFAULT 0 | 首次 AC 前的错误提交数（ACM 罚时依据） |
| penalty | INT | NOT NULL DEFAULT 0 | 罚时（分钟，ACM 用） |
| score | INT | NOT NULL DEFAULT 0 | IOI 分值（每题取历史最高分） |
| is_frozen | BOOLEAN | NOT NULL DEFAULT false | 封榜快照标记，冻结后不再更新 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`contest_id`, `user_id`, `problem_id`)、INDEX(`contest_id`, `is_frozen`)

## 数据所有权

- 比赛中心仅展示公开比赛（`contest_type='public'`）；团队比赛仅在所属团队空间内展示（按 `team_id` 过滤）
- 用户只能查看自己所在团队的比赛；团队比赛仅允许团队成员报名
- 比赛题目访问与提交均校验身份与报名（见下方「关键流程」越权规则）
- 榜单按 `(contest_id, user_id)` 聚合展示；Redis `rank:contest:<id>` 仅作读缓存，权威数据在 `contest_rankings`

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /contests | public | 比赛中心列表（公开） | 分页/状态 | contest[] |
| GET | /contests/{id} | public/owner | 比赛详情（题目/规则/报名状态） | - | contest |
| GET | /contests/{id}/problems | auth（已报名 + 时间窗口） | 比赛题目列表 | - | problem[] |
| POST | /contests | admin/tutor（公开）/ admin/tutor/team_creator/team_admin（团队） | 创建比赛 | contest_type, rule_type, time, register, freeze | contest |
| PUT | /contests/{id} | admin/tutor/team_creator/team_admin | 编辑比赛 | ... | contest |
| POST | /contests/{id}/register | auth | 报名 | - | - |
| GET | /contests/{id}/board | auth | 榜单（封榜时按冻结展示） | - | board |
| GET | /teams/{team_id}/contests | team 角色 | 团队比赛列表 | 分页 | contest[] |
| GET | /users/me/contests | auth | 我的比赛 / 报名列表 | 分页/状态 | contest[] |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 比赛不存在 |
| 2003 | 403 | 未报名 / 非团队成员 / 赛前题目不可见 |
| 3003 | 409 | 重复报名 |
| 3002 | 409 | 报名截止 / 比赛已开始或已结束（不允许补交） |
| 4002 | 429 | 全局判题并发上限触发排队 / 拒绝 |

## 关键流程 / 验收条件

1. **报名**：`POST /contests/{id}/register`——公开比赛所有登录用户可报，团队比赛仅团队成员可报；`contest_registrations` 唯一约束防重复。
2. **比赛访问 / 提交越权校验**：公开比赛须「已注册 + `start_time ≤ now ≤ end_time`」（赛后补题按报名用户开放、不计榜单）；团队比赛须「团队成员 + 已报名」；赛前（`now < start_time`）题目不可见，未报名用户不可见 / 不可提交。比赛提交时 `contest_id` 由服务端从当前请求上下文推导，不信任客户端传入。
3. **计分**（`rule_type` 区分）：
   - **ACM**：全部测试点通过才有分；罚时（分钟）= 首次通过时间（自比赛开始）+ 首次通过前错误提交数 × 罚时系数（默认 20 分钟，可配置）；未通过题目不计罚时；首次通过后错误提交不计入罚时。
   - **IOI**：每题取历史最高分，多次提交取最高、不互相覆盖；总分 = 各题最高分之和（每测试点分值一致）。
4. **榜单条件更新**（避免判题并发覆盖）：
   - 错误提交：`UPDATE ... SET attempts = attempts + 1 WHERE accepted = false AND is_frozen = false`
   - 首次通过：`UPDATE ... SET accepted = true, accepted_at = ..., penalty = ... WHERE accepted = false`（幂等，仅首次生效）
   - IOI：`UPDATE ... SET score = GREATEST(score, :new_score) WHERE is_frozen = false`
5. **封榜 / 解封 / 结束**：由后端周期任务 `contest_transition` 按比赛时间推进——封榜时刻置 `board_frozen=true`、榜单行冻结（`is_frozen`）；结束时解封、重算榜单、置 `status='finished'`、`board_frozen` 复位。封榜期间新提交只落 `submissions` 与 `submission_test_case_results`，不更新榜单行。
6. **赛后补题**：允许补题（`submissions.is_after_contest=true`），不计入榜单。

## 明确不做

- 比赛运行中题目不锁定（不禁止题目在比赛中被编辑）——见 `docs/decisions/2026-08-15-contest-no-lock.md`
- 不做 WebSocket / SSE 实时榜单推送（前端轮询刷新）
- 不允许迟交和补交（但允许赛后补题）
- 不引入 OI / 子任务赛制（当前仅 ACM / IOI）
