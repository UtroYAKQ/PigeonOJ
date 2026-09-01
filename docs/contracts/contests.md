# 比赛模块契约

> 公开 / 团队比赛、报名、实时榜单与封榜。计分按 `rule_type` 区分 ACM / IOI。

## 数据模型

### `contests` — 比赛表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(128) | NOT NULL | 比赛名称 |
| description | TEXT | NULL | 比赛说明（Markdown 渲染） |
| logo | VARCHAR(512) | NULL | 比赛头像（经 `/files/upload/image` 上传的公开 URL；卡片 / 详情横幅展示） |
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
| GET | /contests | public | 比赛中心列表（公开） | 分页/状态/keyword（名称模糊） | contest[] |
| GET | /contests/{id} | public/owner | 比赛详情（题目/规则/报名状态） | - | contest |
| GET | /contests/{id}/problems | auth（已报名 + 时间窗口） | 比赛题目列表 | - | problem[] |
| GET | /contests/{id}/problems/search | admin/tutor（require_manage） | **编排页题目搜索（统一入口）**：已发布且（全站公开 或 本人私有）题目，标题模糊；仅比赛管理角色可调 | 分页/keyword | problem[]（problem_id/title/difficulty） |
| POST | /contests | admin/tutor（公开）/ admin/tutor/team_creator/team_admin（团队） | 创建比赛 | contest_type, logo?, rule_type, time, register, freeze, problems[] | contest |
| PUT | /contests/{id} | admin/tutor/team_creator/team_admin | 编辑比赛 | ... | contest |
| POST | /contests/{id}/register | auth | 报名 | - | - |
| GET | /contests/{id}/board | auth | 榜单（封榜时按冻结展示；BoardCell 含 problem_score 单题满分） | - | board |
| GET | /contests/{id}/board/{user_id}/{problem_id}/accepted | auth（**赛后**：已报名 / admin·tutor） | **榜单单格成功提交**：该 (选手, 题目) 比赛内 AC 提交（不含补题，时间正序）；窗口与角色门控随提交记录 | - | submission[] |
| POST | /contests/{id}/unfreeze | admin/tutor | **手动解冻榜单**：从 submissions 权威重算并回填封榜期间结果（解冻必须人工触发，比赛结束后亦然） | - | contest |
| GET | /contests/{id}/problems/{pid} | auth（已报名 + 看题窗口） | **比赛内题目详情（统一入口）**：归属 / 窗口校验后与 `GET /problems/{id}` 装配一致 | - | problem |
| POST | /contests/{id}/problems/{pid}/submissions | auth（已报名 + 时间窗口） | **比赛交题（统一入口）**：窗口校验后落 contest 提交并派发；赛后自动标记补题（不计榜单） | language/code | submission_id |
| GET | /contests/{id}/submissions | auth（**赛后**：已报名 / admin·tutor） | **比赛提交记录列表**：全员正式提交 + 补题，提交时间倒序；比赛期间对所有人隐藏（403） | 分页 | submission[]（含 nickname / letter） |
| GET | /contests/{id}/submissions/{sid} | auth（**赛后**：已报名 / admin·tutor） | **比赛提交详情（统一入口）**：窗口与 contest 归属校验后复用判题详情装配 | - | submission（含代码 / 测试点明细） |
| GET | /teams/{team_id}/contests | team 角色 | 团队比赛列表（随 teams 模块实现） | 分页 | contest[] |
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
2b. **题目编排规则**：可编排题目 = 已发布且（全站公开 **或 本人私有**）；编排保存与编排搜索端点按同一规则校验；参赛者经比赛窗口查看比赛内题目时按比赛访问权限放行（题解 / 测试点等管理数据仍按题目权限门控）。
3. **计分**（`rule_type` 区分）：
   - **ACM**：全部测试点通过才有分；罚时（分钟）= 首次通过时间（自比赛开始）+ 首次通过前错误提交数 × 罚时系数（默认 20 分钟，可配置）；未通过题目不计罚时；首次通过后错误提交不计入罚时；提交分数原生二值（AC=满分否则 0），派题携带短路标记（judge.md「赛制计分」）。
    - **IOI**：每题取历史最高分，多次提交取最高、不互相覆盖；总分 = 各题最高分之和（每测试点分值一致，提交分数 = 通过测试点比例 × 单题分值）。
4. **榜单条件更新**（避免判题并发覆盖）：
   - 错误提交：`UPDATE ... SET attempts = attempts + 1 WHERE accepted = false AND is_frozen = false`
   - 首次通过：`UPDATE ... SET accepted = true, accepted_at = ..., penalty = ... WHERE accepted = false`（幂等，仅首次生效）
   - IOI：`UPDATE ... SET score = GREATEST(score, :new_score) WHERE is_frozen = false`
5. **封榜 / 解冻 / 结束**（修订：解冻必须人工）：封榜由周期任务 `contest_transition` 按时间
   自动触发（结束前 `freeze_offset_seconds` 秒置 `board_frozen=true`、榜单行冻结 `is_frozen`）；
   **解冻只能由 admin/tutor 调 `POST /contests/{id}/unfreeze` 手动执行**——从 submissions
   权威重算榜单并回填封榜期间结果；比赛结束（`status='finished'`）**不自动解冻**，榜单保持
   冻结快照直到人工解冻。封榜期间新提交只落 `submissions` 与 `submission_test_case_results`，
   不更新榜单行。
6. **赛后补题**：允许补题（`submissions.is_after_contest=true`），不计入榜单。
7. **提交记录可见性**（比赛上下文统一入口端点）：
   - **比赛期间（`now < end_time`）对所有人隐藏**（含参赛者本人与管理角色，返回 2003）；
     前端「提交记录」tab 在此窗口内展示提示、不发起列表请求
   - **赛后**：已报名用户与 admin/tutor 可见全部比赛提交（含补题行），列表含提交人昵称与题号；
     未报名用户不可见（2003）
   - 提交详情经比赛上下文端点 `GET /contests/{id}/submissions/{sid}` 读取（不跨模块直调
     `GET /submissions/{id}`，后者仍仅限本人）；装配复用 `SubmissionService.build_detail`
   - 详情校验按 `(contest_id, submission_id, submit_type='contest')` 归属查询，
     不信任客户端 contest_id
8. **榜单单格成功提交**：榜单 BoardCell 携带 `problem_score`（单题满分，前端做分母）；
   赛后点击通过格可调 `GET /contests/{id}/board/{user_id}/{problem_id}/accepted`
   查看该格「当时成功」的提交——仅该 (选手, 题目) 比赛内 AC（不含补题，时间正序）；
   可见性随第 7 条提交记录窗口（比赛期间对所有人隐藏，赛后参赛者与管理角色）；
   格子内提交行可点击进入上下文内评测结果页。封榜冻结格不可点击。

## 明确不做

- 比赛运行中题目不锁定（不禁止题目在比赛中被编辑）
- 不做 WebSocket / SSE 实时榜单推送（前端轮询刷新）
- 不允许迟交和补交（但允许赛后补题）
- 不引入 OI / 子任务赛制（当前仅 ACM / IOI）

## 实现状态

- 已实现（迁移 0019 / 0020）：全站比赛端到端——建赛编排 / 报名 / 赛内题目与交题（统一入口）/
  ACM·IOI 计分与榜单条件更新 / 自动封榜 / **手动解冻重算** / 赛后补题；
  周期任务 `contest_transition`（开赛 / 自动封榜 / 结束，随应用 lifespan 启动）
- 已实现：提交行原生赛制快照（`submissions.rule_type`，迁移 0020）——ACM 二值计分 +
  派题 `stop_on_failure` 短路（首个失败点后不测后续点），IOI 部分计分；计分与可见性
  不再依赖比赛时间判断（judge.md「赛制计分」）
- 已实现：比赛提交记录端点（列表 + 详情，赛后开放；第 7 条）；比赛详情页「提交记录」tab
  （比赛期间展示提示，赛后分页列表，行点击进上下文内评测结果页 `/contests/:cid/submissions/:sid`）；
  详情页 tab 内容纵向伸展，分页条固定在内容区底部
- 已实现：榜单视觉重设计（排名 / 选手列固定左侧，双行题头 = 题号 + IOI 单题满分，
  AC / 部分分 / 尝试 / 未提交药丸格 + 图例，flex-height 表体滚动 + 分页贴底）；
  赛后点击 AC 格弹窗查看该格成功提交（`GET .../board/{user_id}/{problem_id}/accepted`，第 8 条）
- 前端：比赛中心为**卡片流**（头像横幅 + 状态徽标 + 赛制 / 题数 / 报名数 / 时间窗，整卡点击进详情；
  无头像回退渐变底 + 标题首字），建赛 / 编辑为**全页表单**（`/admin/contests/create`、
  `/admin/contests/:id/edit`：logo 上传 + Markdown 说明 + 时间四元组 + 题目编排），
  详情页带 logo 横幅与 Markdown 说明渲染；榜单页轮询刷新
- 待 teams 模块：团队比赛（`team_id` / `contest_type='team'` 列与约束已落库，
  报名与团队列表端点随 teams 开放）
