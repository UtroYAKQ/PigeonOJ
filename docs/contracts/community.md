# 社区模块契约

> 站内通知、私信、题解（官方题解展示 + 用户题解分享）、代码广场、讨论区、评论与举报。
>
> **实现状态**：题解（含官方题解端点）、代码广场、评论、举报（用户创建 + 管理处理）已实现；
> 通知 / 私信 / 讨论区为规划项，模型先行留档、端点未实现。

## 数据模型

### `code_shares` — 代码广场分享表

用户在代码广场便捷分享代码片段 / 题解代码：结构化字段（语言 + 代码 + 可选关联题目），
区别于题解（围绕某道题的解法说明）与讨论区帖子（规划）。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 作者 |
| title | VARCHAR(255) | NOT NULL | 标题 |
| description | TEXT | NULL | 说明（Markdown，≤64KB UTF-8 字节；插图走 `POST /files/upload/image`） |
| language | VARCHAR(32) | NOT NULL | 代码语言，首批与判题语言一致：`cpp17` / `python3.12` / `java21` |
| code | TEXT | NOT NULL | 代码原文（≤64KB UTF-8 字节，与提交代码上限一致） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'published' | `published` / `removed`（无草稿态：便捷分享直接发布） |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`status`, `created_at`)、INDEX(`user_id`, `status`)

CHECK：`status IN ('published','removed')`、`language IN ('cpp17','python3.12','java21')`

### `solutions` — 用户题解表

区别于题目表的官方 `solution` 字段（展示入口见「官方题解」节）。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| user_id | UUID | NOT NULL, FK → users.id | 作者 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NOT NULL | 题解正文（Markdown，≤64KB UTF-8 字节；插图走 `POST /files/upload/image`） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'published' | `published` / `removed`（无草稿态；CHECK 保留 `draft` 仅为存量库兼容） |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `status`)、INDEX(`user_id`, `status`)

CHECK：`status IN ('draft','published','removed')`

### `comments` — 评论表

支持对题解（后续扩展题目 / 帖子等）的评论与回复，两级结构。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| target_type | VARCHAR(32) | NOT NULL | `solution`（一期唯一开放值；CHECK 约束预留 `problem` / `post` / `submission`） |
| target_id | UUID | NOT NULL | 目标对象 ID |
| parent_id | UUID | NULL, FK → comments.id | 回复的父评论；**仅允许挂在一级评论上**（父评论的 parent_id 必须为 NULL），不提供三级楼中楼 |
| content | TEXT | NOT NULL | ≤2000 字符 |
| is_deleted | BOOLEAN | NOT NULL DEFAULT false | 删除（软） |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`target_type`, `target_id`, `created_at`)、INDEX(`parent_id`)

CHECK：`target_type IN ('solution','code_share','problem','post','submission')`（API 层仅开放 `solution`）

### `reports` — 举报表（admin 模块承载存储，见 admin.py）

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| reporter_id | UUID | NOT NULL, FK → users.id | 举报人 |
| target_type | VARCHAR(32) | NOT NULL | `problem` / `solution` / `post` / `comment` / `user` |
| target_id | UUID | NOT NULL | |
| reason | TEXT | NOT NULL | 举报理由 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'pending' | `pending` / `handled` / `ignored` |
| handled_by | UUID | NULL, FK → users.id | 处理人 |
| handled_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`status`, `created_at`)

### `notifications` — 站内通知表（规划，未实现）

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 接收者 |
| type | VARCHAR(32) | NOT NULL | `team_apply` / `team_approval` / `contest` / `comment` / `system` 等 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NULL | |
| related_type | VARCHAR(32) | NULL | 关联对象类型 |
| related_id | UUID | NULL | 关联对象 ID |
| is_read | BOOLEAN | NOT NULL DEFAULT false | |
| read_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `is_read`, `created_at DESC`)

### `messages` — 站内消息表（私信，规划，未实现）

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| sender_id | UUID | NOT NULL, FK → users.id | 发送者 |
| receiver_id | UUID | NOT NULL, FK → users.id | 接收者 |
| content | TEXT | NOT NULL | |
| is_read | BOOLEAN | NOT NULL DEFAULT false | |
| read_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`receiver_id`, `is_read`, `created_at`)

### `posts` — 讨论区帖子表（规划，未实现）

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 发帖人 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NOT NULL | Markdown |
| category | VARCHAR(32) | NULL | 板块 / 分类 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'published' | `published` / `removed` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`status`, `created_at DESC`)

## 官方题解

- 官方题解即 `problems.solution`（Markdown），编辑入口沿用写题向导（见 `problems.md`），本模块只负责**展示**：
  `GET /problems/{problem_id}/editorial` 面向**可通过题目可见性检查的任何人**返回内容
  （`problems.md` 数据所有权节；题目草稿仍仅管理者可见，`can_manage` 随响应返回）。
- 前端展示收口到题解页「官方题解」tab；题目详情不再内联渲染官方题解
  （`GET /problems/{id}` 的 `solution` 字段保留，仍仅管理者可读，供编辑回显）。
- 写题页（双栏工作台）提供「题解」入口按钮，跳转当前上下文内的题解页。

## 比赛防作弊门禁

题目被任意 **进行中**（`contests.status='running'`，比赛状态推进循环维护）的比赛引用时
（`contest_problems` 关联），该题的全部社区内容——官方题解、分享题解（列表 / 详情）、
评论的读与写——一律拒绝（`3002`，409）。全局隐藏而非仅对参赛者隐藏：非参赛者可见即可转发作弊。
比赛结束（`finished`）后自动开放。

## 社区功能开关

- 配置键 `community.feature_switches`（category=`community`，JSONB，见 `admin.md`）：
  `{"solutions": true, "comments": true, "codes": true}`；缺省键视为开启。
- `solutions=false`：题解创建 / 编辑 / 下架拒绝（`3002`），官方题解与题解浏览不受影响；
- `comments=false`：评论创建拒绝（`3002`），浏览不受影响；
- `codes=false`：代码分享创建 / 删除拒绝（`3002`），浏览不受影响。

## 代码广场行为要点

- 发布无草稿态，直接 `published`；60s 冷却（4002）；
- 关联题目（`problem_id` 非空）被进行中比赛引用时：创建 3002、详情 3002、**列表过滤**；
- `removed` 态仅作者与 admin 可读（404 不泄漏存在性），恢复仅经 admin 端点。

## 数据所有权

- 通知按接收者隔离：所有查询必须带 `WHERE user_id = ?`（接收者）；标记已读仅本人可操作（规划）
- 私信：只能读自己的收发消息（`sender_id = ?` 或 `receiver_id = ?`）（规划）
- 题解：草稿仅作者可见；已发布内容对**可访问该题目的用户**可见；`removed` 对外不可见
  （作者与 admin 仍可读详情，用于恢复 / 取证）。题目可见性继承：题解 / 评论的一切读写
  先过题目访问检查（复用 `ProblemService.get_detail` 的可见性门控），
  组织题 / 团队快照题 / 私密题的题解不向无权用户泄漏
- 团队快照题（`source_problem_id` 非空）沿用题库裸路径拦截语义：非 admin 走裸端点一律 2003，
  团队上下文不提供题解入口
- 评论软删除（`is_deleted=true`），不物理删除；软删评论若存在未删回复，列表返回占位行
  （`content=null`、作者置空），无未删回复则整行隐藏；admin 经 `include_deleted=true` 查看全部
- 举报人身份不向被举报方暴露
- 管理操作（下架他人题解、软删 / 恢复评论、处理举报）仅 `admin`

## 端点

统一前缀 `/api/v1`。分页契约见 `common.md`（`?page=1&page_size=20`）。

### 题解

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problems/{pid}/editorial | 题目可见者 | 官方题解内容；比赛进行中 3002 | - | `{solution: string\|null, can_manage}` |
| GET | /problems/{pid}/solutions | 题目可见者 | 分享题解分页（published；`mine=true` 返回本人全部状态，需登录） | 分页/keyword（标题模糊）/mine | solutionSummary[]（含作者摘要、评论数、excerpt=正文前 200 字符） |
| POST | /problems/{pid}/solutions | auth | 创建题解（直接发布）；需题目访问权；比赛进行中 / 开关关闭 3002；60s 频控 4002 | title, content | solutionDetail |
| GET | /solutions/{id} | published→题目可见者；draft/removed→作者或 admin | 题解详情（全文） | - | solutionDetail |
| PUT | /solutions/{id} | owner | 编辑标题 / 正文（`removed` 态不可改 3002，恢复走 admin 端点） | title?, content? | solutionDetail |
| DELETE | /solutions/{id} | owner / admin | 下架（`removed`，软删；幂等） | - | - |

### 代码广场

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /codes | public | 分享分页（published；`mine=true` 返回本人全部状态，需登录） | 分页/keyword（标题+说明模糊）/language/mine | codeShareSummary[]（含作者） |
| POST | /codes | auth | 发布分享；开关关闭 3002；关联题比赛进行中 3002；60s 频控 4002 | title, language(`cpp17`\|`python3.12`\|`java21`), code(≤64KB), description?, problem_id? | codeShareDetail |
| GET | /codes/{id} | published→所有人；removed→作者或 admin；关联题比赛进行中 3002 | 分享详情（含代码原文） | - | codeShareDetail |
| DELETE | /codes/{id} | owner / admin | 下架（`removed`，软删；幂等） | - | - |

### 评论

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /comments | 题目可见者 / 分享可见者 | 一级评论分页（created_at 升序），每条附前 2 条回复 + `reply_count`；`parent_id=` 取单条评论的回复分页；admin 专有 `include_deleted=true` 含软删行 | target_type(`solution`\|`code_share`)/target_id/分页/parent_id?/include_deleted? | comment[] |
| POST | /comments | auth | 发表评论 / 回复；开关关闭 / 目标不可评（题解已下架、父评论已删、父评论非一级）3002；10s 频控 4002 | target_type, target_id, parent_id?, content(≤2000) | comment |
| DELETE | /comments/{id} | owner / admin | 软删（`is_deleted=true`；幂等） | - | - |

### 举报

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /reports | auth | 举报题解 / 代码分享 / 评论等；同用户同目标 pending 中重复举报 3003；60s 频控 4002 | target_type, target_id, reason | - |
| GET | /admin/reports | admin | 举报列表 / 处理（admin 模块端点，见 admin.md）；列表行回填 `target_summary`（题解标题 / 评论正文截断 / 题目标题） | 分页/状态 | report[] |

### 管理端点

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /admin/solutions | admin | 题解管理列表（全状态） | 分页/status/keyword（标题+内容模糊）/problem_id | adminSolution[]（含题目、作者、评论数） |
| PUT | /admin/solutions/{id}/status | admin | 下架 / 恢复（`removed` ⇄ `published`） | status | - |
| GET | /admin/codes | admin | 代码分享管理列表（全状态，created_at 倒序） | 分页/status/keyword/language | adminCodeShare[]（含作者） |
| PUT | /admin/codes/{id}/status | admin | 下架 / 恢复（`removed` ⇄ `published`） | status | - |
| PUT | /admin/comments/{id}/status | admin | 软删 / 恢复评论 | is_deleted | - |

> 题解详情预览复用 `GET /solutions/{id}`（admin 经可见性门控天然可读）；被删评论经
> `GET /comments?...&include_deleted=true` 读取。管理后台不设独立评论列表页：
> 评论一律从题解管理行的预览弹窗下钻（见 frontend.md）。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题解 / 评论 / 举报不存在 |
| 2003 | 403 | 越权操作他人内容（非 owner / admin）；题目不可见继承拦截 |
| 3002 | 409 | 状态冲突：比赛进行中门禁、功能开关关闭、目标已下架 / 不可评、removed 态编辑 |
| 3003 | 409 | 重复举报（同用户同目标 pending 中） |
| 4001 | 429 | 发送过频 |
| 4002 | 429 | 触发限流（题解 60s / 评论 10s / 举报 60s 冷却，Redis 固定窗口） |

## 关键流程 / 验收条件

1. **官方题解**：可访问题目的用户拉取 `editorial`；比赛进行中 3002；草稿题仅管理者可读（`can_manage=true`）。
2. **题解生命周期**：作者创建（直接 `published`，无草稿态）→ `PUT` 编辑标题 / 正文 →
   `DELETE` 下架（对外消失，作者与 admin 仍可读）→ admin 可恢复（`published`）；
   作者对 `removed` 态无编辑权（防与治理对抗），内容仍可读可复制。
3. **评论 / 回复**：评论挂 `solution`（一级）或挂一级评论（`parent_id`，仅两级）；
   软删评论有未删回复时返回占位行；题解 `removed` 后其评论随内容一起对外隐藏且不可再评。
4. **题目可见性继承**：组织题 / 私密题的题解与评论对无权用户一律 2003（含枚举不存在时同样回包，
   不泄漏资源存在性）。
5. **比赛门禁**：进行中比赛引用的题目，题解 / 评论读写全部 3002，比赛结束自动恢复。
6. **举报**：`auth` 用户举报 → `admin` 处理（`handled` / `ignored`）；管理端从举报行跳转
   题解管理预览（锚定被举报评论）。
7. **功能开关**：`community.feature_switches` 关闭后写操作 3002、浏览不受影响。

## 明确不做

- 评论物理删除（软删除，保留审计）
- 评论三级楼中楼（`parent_id` 仅允许挂一级评论）
- 题解 / 评论点赞与排序（后续扩展）
- 评论站内通知（随 `notifications` 模块落地，P2）
- 团队快照题的题解 / 评论（团队上下文封闭，团队题目为快照复制题，见 teams.md）
- 独立管理后台评论列表页（评论治理从题解管理预览下钻 + 举报定位）
- 代码广场评论与题目关联（分享即贴代码，讨论在题解侧）
