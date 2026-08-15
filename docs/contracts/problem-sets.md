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
- 管理题单（创建 / 编辑 / 编排题目）仅 `admin/tutor/team_creator/team_admin`

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problem-sets | public | 题单列表 | 分页 | problem_set[] |
| POST | /problem-sets | admin/tutor/team_creator/team_admin | 创建题单 | team_id?/title/visibility | problem_set |
| PUT | /problem-sets/{id}/items | admin/tutor/team_creator/team_admin | 编排题目 | items[{problem_id, sort}] | - |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题单不存在 |
| 2003 | 403 | 越权管理非本人 / 非团队题单 |
| 3003 | 409 | 题目重复加入题单 |

## 关键流程 / 验收条件

1. **创建题单**：公开题单由 `admin/tutor` 创建（`team_id` 为空）；团队题单由团队创建者 / 管理员创建（`team_id` 必填，`visibility='team'`）。
2. **编排题目**：`PUT /problem-sets/{id}/items` 全量替换题目列表；题目从可访问题目中选择（团队题单可选公开题库或团队题库题目）。
3. **刷题**：题单内题目按 `sort_order` 展示，但刷题不强制按顺序完成。

## 明确不做

- 题单不做物理删除，下线走 `status='archived'`
- 团队题单不进入题单中心（仅团队空间内展示）
