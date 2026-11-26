# 题单模块契约

> 公开题单与团队题单，按配置顺序编排题目。

## 数据模型

### `problem_sets` — 题单表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(128) | NOT NULL | 题单标题 |
| description | TEXT | NULL | 题单说明 |
| team_id | UUID | NULL, FK → teams.id | 归属团队；NULL=全站题单，非 NULL=团队题单 |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者 |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | `public` / `private` / `team_visible`；全站题单用 public/private，团队题单恒 team_visible（全队可见；原 `admin_visible` 分支随迁移 0043 移除并回填 team_visible） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `archived` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK 约束（归属与可见性匹配）：

```sql
CHECK (
  (team_id IS NULL     AND visibility IN ('public','private')) OR
  (team_id IS NOT NULL AND visibility IN ('team_visible'))
)
```

索引：INDEX(`owner_id`, `status`)、INDEX(`team_id`, `visibility`)

### `problem_set_items` — 题单题目关联表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_set_id | UUID | NOT NULL, FK → problem_sets.id | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| sort_order | INT | NOT NULL DEFAULT 0 | 题单内展示顺序 |
| added_by | UUID | NOT NULL, FK → users.id | 添加人 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`problem_set_id`, `problem_id`)、INDEX(`problem_id`)

## 数据所有权

- 题单中心仅展示公开题单（`visibility='public'`、`team_id` 为空）；「我的」勾选
  （mine=true）为本人未下线的**全站**题单（团队题单属封闭空间不进题单中心）
- 团队题单仅在所属团队空间内展示（按 `team_id` 过滤），不进入题单中心；团队题单
  **恒 `team_visible`（全队成员可见）**——创建无可见性入参、后端一律落 team_visible、
  编辑不可修改，manager_chain 无可见性门（迁移 0043 移除 admin_visible 分支并回填存量）；
  团队题单的
  创建 / 复制来源 / 编排 / 下线 / 详情浏览 / 题单内题目 / 交题 / 自测全部走
  teams.md 团队空间节独立端点（`/teams/{team_id}/problem-sets/...` 前缀，
  限界上下文隔离，不走本模块统一入口 `GET /problem-sets/{id}`）
- 团队题单内编排候选 = 已发布且（本团队题目 ∪ 全站公开；组织题须先引用进团队，本人私有分支随个人出题取消移除）；
  全站题单编排一律排除团队题目（`team_id` 非空，封闭空间隔离）
- 题单内题目展示受题目自身可见性约束（见 `problems.md`）；用户在题单中访问题目时按题单访问权限展示题面
- 管理题单（创建 / 编辑 / 编排题目）角色门：全站题单 = `admin`（tutor 已下线）；团队题单 = team_creator/team_admin；
  **单个题单的管理权按单一所有权模型判定**：`admin` 可管理全站题单，其余管理角色仅可管理本人创建的题单；
  团队题单由团队创建者 / 管理员管理

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problem-sets | public / auth | 题单中心列表：仅公开且未下线的全站题单；`mine=true`（题单中心「我的」勾选，须登录，匿名 401）改为仅本人未下线题单（含私有） | 分页/keyword/mine | problem_set[]（含 item_count） |
| POST | /problem-sets | admin | 创建全站题单（team_id 为空；`visibility='team'` 分支拒绝 1001；tutor 已下线，公开内容收归 admin） | title/description?/visibility | problem_set |
| GET | /problem-sets/{id} | public/owner | 题单详情：条目按 `sort_order` 展示，携带题目元信息（title / difficulty / time_limit_ms / memory_limit_mb）；登录请求条目带 `solved` 作答状态（`true`=已通过 / `false`=已尝试未通过 / `null`=未提交过，未登录恒 `null`，口径与题库列表一致）；私有 / 已下线题单仅创建者与管理角色可见（2003），`can_manage` 标记管理入口 | - | problem_set_detail |
| GET | /admin/problem-sets | admin | 题单管理视图：admin 全量（含私有与已下线），供管理后台编排维护；`ownership` 过滤来源（`solo`=全站题单 / `team`=团队题单，非法值 1001）；列表项带 `team_id`（区分来源） | 分页/keyword/status/ownership | problem_set[]（含 item_count / team_id） |
| GET | /problem-sets/{id}/problems/{pid} | public/owner | **题单内题目详情（统一入口）**：题单可见 + 题目属于该题单校验（题目不属于该题单 3001）后，返回与 `GET /problems/{id}` 完全一致的详情装配；题单上下文内前端只调本端点 | - | problem |
| POST | /problem-sets/{id}/problems/{pid}/submissions | auth | 题单内交题：题单须可见（私有 / 已下线按可见性拦截 2003）、题目必须属于该题单（否则 3001）；落库 / 派发 / 计分与 `POST /submissions` 完全一致（`submit_type='practice'`） | language/code（≤64KB） | submission_id / status |
| PUT | /problem-sets/{id} | admin（全站题单）/ team_creator·team_admin（团队题单） | 编辑题单元信息（title / description / visibility 缺省不动；团队题单 visibility 不可修改，传入变更 1001） | title?/description?/visibility? | problem_set |
| PUT | /problem-sets/{id}/items | admin（全站题单）/ team_creator·team_admin（团队题单） | 编排题目：全量替换题单内列表；全站题单可编排 = 已发布且（全站公开 或 admin 本人私有），一律排除团队 / 组织题目；团队题单可编排 = 已发布且（本团队题目 ∪ 全站公开）；草稿 / 归档返回 1001；同一题单内重复返回 3003 | items[{problem_id, sort_order}] | - |
| POST | /problem-sets/{id}/archive | admin（全站题单）/ team_creator·team_admin（团队题单） | 下线题单（`status='archived'`，退出题单中心；创建者 / 管理角色仍可直接访问详情） | - | problem_set |

> 团队题单端点已随 teams.md 团队空间节实现（创建 / 编排 / 下线 /
> 列表走 `/teams/{team_id}/problem-sets*` 独立端点）；`team_id` 列、CHECK 约束与
> `referenced_at` 来源字段已落库（迁移 0018 / 0022 / 0029），团队题单恒 `team_visible`
> 随迁移 0043 收紧（见「数据模型」与 teams.md 实现状态）。

## 当前基础前端页面

前台提供 `/problem-sets` 题单中心（分页 + 关键字搜索，仅浏览）与 `/problem-sets/{id}` 题单详情
刷题页（题目按顺序展示、点击进入题目工作台）；管理角色在详情页有「前往管理」入口。
题单管理（含私有与已下线的全量管理视图）统一收敛在管理后台 `/admin/problem-sets`
（admin 可见）：列表 + 「题单详情」页（元信息概览 + 「编排题目」按钮 + 编辑信息 / 下线；
编排弹窗为列表页与详情页共享组件）。详情页点击题目仅打开只读预览（不跳题库 / 不进写题页，
见「关键流程」第 4 条）。团队题单页随 teams 模块实现。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题单不存在 |
| 2003 | 403 | 越权管理非本人 / 非团队题单；私有 / 已下线 / 团队题单对无权限者不可见 |
| 3003 | 409 | 题目重复加入题单（同一题单内 problem_id 重复） |
| 1001 | 400 | 团队题单暂未开放 / 编排含未发布或不可见题目（含团队题目编入全站题单）/ 可见性非法 |

## 关键流程 / 验收条件

1. **创建题单**：公开题单由 `admin` 创建（`team_id` 为空；tutor 已随组织化改造下线）；团队题单由团队创建者 / 管理员创建（`team_id` 必填，恒 `team_visible`，无可见性入参）。
2. **编排题目**：`PUT /problem-sets/{id}/items` 全量替换题目列表；全站题单可编排 = 已发布且（全站公开 或 admin 本人私有），一律排除团队 / 组织封闭空间题目（admin 亦然）；团队题单可编排 = 已发布且（本团队题目 ∪ 全站公开），与比赛编排规则一致。私有题编入题单即视为经题单分发：题单上下文（`GET /problem-sets/{id}/problems/{pid}` 与题单内交题）凭题单可见 + 归属校验放行（bypass 题目可见性）；题库裸路径（直访详情 / `POST /submissions` 直提 / 提交列表 / 自测）仍按题目可见性严格校验——私有题仅创建者与 admin 可从题库侧访问。
3. **刷题**：题单内题目按 `sort_order` 展示，但刷题不强制按顺序完成；题单上下文写题页经
   题单交题接口提交（题目归属校验通过后复用统一判题链路），评测结果在题单路由内查看。
4. **管理端题目访问约束（契约级）**：管理后台 `/admin/problem-sets/:setId`（题单详情）内点击题目
   仅打开**只读题目预览**（`/admin/problem-sets/:setId/problems/:pid/preview`，位于题单详情
   下级路由；面包屑 管理后台/题单管理/题单详情/题目预览），
   **禁止跳转题库写题页**（`/problems/:id` 或 `/problem-sets/:setId/problems/:pid`）
   ——管理端不承载作答入口，写题页仅由前台题单中心 / 题库进入。
5. **模块统一入口（Facade 门面）**：题单上下文内对题目的读 / 写经题单模块自己的端点完成
   （详情 `GET /problem-sets/{id}/problems/{pid}`、交题 `POST .../submissions`），
   前端不跨模块直调题库端点（迪米特法则）；端点入口校验归属关系（题单可见 + 题目属于该题单，
   嵌套资源路径即约束），装配与判题链路复用题库 / judge 统一实现，保证两入口行为一致。
   上下文隔离通用规范见 `docs/frontend.md`「路由上下文隔离」
   （限界上下文 / 门面 / 迪米特法则的术语对齐见该节）。

## 明确不做

- 题单不做物理删除，下线走 `status='archived'`
- 团队题单不进入题单中心（仅团队空间内展示）

## 实现状态

- 已实现（迁移 0018）：全站题单端到端——题单中心列表 / 详情刷题页 / 创建 / 编辑 / 编排 / 下线；
  创建与编辑权限按契约收敛为 `admin`（全站题单；tutor 已下线）
- 已实现（迁移 0029，随 teams.md 团队空间节）：团队题单（创建 / 编排 /
  下线 / 列表走团队端点；详情复用本模块端点并对团队成员放行）；
  团队题目进入团队题单的编排候选随之放开；全站编排排除团队题目
- 已实现（迁移 0043，团队题单可见性收敛）：移除团队题单 `admin_visible` 分支，团队题单
  恒 `team_visible`（全队成员可见）——创建 / 编辑无可见性入参、后端一律写 team_visible、
  团队分支 CHECK 收紧为仅 `team_visible`、存量 admin_visible 回填 team_visible
  （原 0032 双分支随本迁移下架销毁，详见 teams.md 实现状态）
