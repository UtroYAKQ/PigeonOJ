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
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | `public` / `private` / `team`；全站题单用 public/private，团队题单用 team |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `archived` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK 约束（归属与可见性匹配）：

```sql
CHECK (
  (team_id IS NULL     AND visibility IN ('public','private')) OR
  (team_id IS NOT NULL AND visibility = 'team')
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

- 题单中心仅展示公开题单（`visibility='public'`、`team_id` 为空）
- 团队题单仅在所属团队空间内展示（按 `team_id` 过滤），不进入题单中心
- 题单内题目展示受题目自身可见性约束（见 `problems.md`）；用户在题单中访问题目时按题单访问权限展示题面
- 管理题单（创建 / 编辑 / 编排题目）角色门为 `admin/tutor/team_creator/team_admin`；
  **单个题单的管理权按单一所有权模型判定**：`admin` 可管理全站题单，其余管理角色仅可管理本人创建的题单

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problem-sets | public | 题单中心列表：仅公开且未下线的全站题单 | 分页/keyword | problem_set[]（含 item_count） |
| POST | /problem-sets | admin/tutor | 创建题单（team_id 为空；`visibility='team'` 随 teams 模块开放，当前返回 1001） | title/description?/visibility | problem_set |
| GET | /problem-sets/{id} | public/owner | 题单详情：条目按 `sort_order` 展示，携带题目元信息（title / difficulty / time_limit_ms / memory_limit_mb）；登录请求条目带 `solved` 作答状态（`true`=已通过 / `false`=已尝试未通过 / `null`=未提交过，未登录恒 `null`，口径与题库列表一致）；私有 / 已下线题单仅创建者与管理角色可见（2003），`can_manage` 标记管理入口 | - | problem_set_detail |
| GET | /admin/problem-sets | admin/tutor | 题单管理视图：admin 全量、tutor 仅本人创建（含私有与已下线），供管理后台编排维护 | 分页/keyword/status | problem_set[]（含 item_count） |
| GET | /problem-sets/{id}/problems/{pid} | public/owner | **题单内题目详情（统一入口）**：题单可见 + 题目属于该题单校验（题目不属于该题单 3001）后，返回与 `GET /problems/{id}` 完全一致的详情装配；题单上下文内前端只调本端点 | - | problem |
| POST | /problem-sets/{id}/problems/{pid}/submissions | auth | 题单内交题：题单须可见（私有 / 已下线按可见性拦截 2003）、题目必须属于该题单（否则 3001）；落库 / 派发 / 计分与 `POST /submissions` 完全一致（`submit_type='practice'`） | language/code（≤64KB） | submission_id / status |
| PUT | /problem-sets/{id} | admin/tutor | 编辑题单元信息（title / description / visibility，缺省不动） | title?/description?/visibility? | problem_set |
| PUT | /problem-sets/{id}/items | admin/tutor/team_creator/team_admin | 编排题目：全量替换题单内列表；题目须为已发布的全站公开题目（草稿 / 私有 / 团队题目返回 1001），同一题单内重复返回 3003 | items[{problem_id, sort_order}] | - |
| POST | /problem-sets/{id}/archive | admin/tutor | 下线题单（`status='archived'`，退出题单中心；创建者 / 管理角色仍可直接访问详情） | - | problem_set |

> 团队题单端点（`GET /teams/{team_id}/problem-sets` 等）随 teams 模块一并实现；
> `team_id` 列与 CHECK 约束已按本契约落库（迁移 0018），teams 表建立后补 FK。

## 当前基础前端页面

前台提供 `/problem-sets` 题单中心（分页 + 关键字搜索，仅浏览）与 `/problem-sets/{id}` 题单详情
刷题页（题目按顺序展示、点击进入题目工作台）；管理角色在详情页有「前往管理」入口。
题单管理（含私有与已下线的全量管理视图）统一收敛在管理后台 `/admin/problem-sets`
（`admin/tutor` 可见）：列表 + 「题单详情」页（元信息概览 + 「编排题目」按钮 + 编辑信息 / 下线；
编排弹窗为列表页与详情页共享组件）。详情页点击题目仅打开只读预览（不跳题库 / 不进写题页，
见「关键流程」第 4 条）。团队题单页随 teams 模块实现。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题单不存在 |
| 2003 | 403 | 越权管理非本人 / 非团队题单；私有 / 已下线题单对无权限者不可见 |
| 3003 | 409 | 题目重复加入题单（同一题单内 problem_id 重复） |
| 1001 | 400 | 团队题单暂未开放 / 编排含未发布或不可见题目 / 可见性非法 |

## 关键流程 / 验收条件

1. **创建题单**：公开题单由 `admin/tutor` 创建（`team_id` 为空）；团队题单由团队创建者 / 管理员创建（`team_id` 必填，`visibility='team'`）。
2. **编排题目**：`PUT /problem-sets/{id}/items` 全量替换题目列表；题目从可访问题目中选择（团队题单可选公开题库或团队题库题目）。
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
  创建与编辑权限按契约收敛为 `admin/tutor`（团队角色待 teams 模块）
- 待 teams 模块：团队题单（`team_id` / `visibility='team'` 列与约束已落库，应用层暂拒绝创建）；
  团队题库题目（`team_id` 列落地后）加入团队题单的候选范围随之放开
