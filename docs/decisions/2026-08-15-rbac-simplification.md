# RBAC 简化：不设权限表，按角色 code 分支

- 日期：2026-08-15
- 状态：已采纳

## 背景

需求需要全局角色（admin / tutor / user）与团队角色（team_creator / team_admin / team_member）共同决定功能权限。最初的候选方案是经典的「角色 — 权限」多对多建模（`roles`、`permissions`、`role_permissions` 三张表）。

## 决策

删除 `permissions` 与 `role_permissions` 表。功能权限不落表，由中间件从 `roles`（静态种子）+ `user_roles`（运行时授权）装载角色（含 `scope` / `object_id`）后，按角色 `code` 在应用层分支判定。

- 角色表保留：`roles`（code / name / scope）、`user_roles`（user_id / role_id / scope / object_id / assigned_by）
- `scope` 标定生效范围（global/team），`object_id` 标定生效对象（global 为 NULL，team 为团队 id）
- 资源级可见性（题目 / 题单 / 比赛）由查询层按 `owner_id / team_id / visibility` 过滤，不依赖权限表

## 原因

- 角色集合固定（6 个）、权限矩阵稳定，功能权限与角色一一对应；逐权限落表会引入「一处改矩阵、多处同步」的维护成本
- 团队资源上下文（`scope='team'` + `object_id=<team_id>`）用 `user_roles` 统一表达，团队角色天然带范围语义
- 判定集中在应用层，新增能力只需改一个分支函数，测试覆盖更直接

## 替代方案

- **经典 RBAC（permissions / role_permissions 表）**：被否决——角色固定、矩阵稳定时表化收益低、成本高
- **统一权限点注解 + 装饰器**：判定仍落在应用层，与「按 code 分支」等价，仅实现形态差异，不做表化

## 影响

- 接口权限列直接标注角色 code（见 `docs/decisions/2026-08-15-permission-column.md`）
- 无权限表，新功能权限判定在 Service / 中间件按角色分支
- 团队角色仅 `scope='team'` + `object_id=<team_id>` 时叠加生效
