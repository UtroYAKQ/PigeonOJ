# 团队模块契约

> 团队、成员、加入申请与邀请链接。团队角色经 `user_roles`（`scope='team'`、`object_id=<team_id>`）统一授权，见 `docs/security.md`。

## 数据模型

### `teams` — 团队表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL | 团队名称 |
| description | TEXT | NULL | 团队简介 |
| avatar_url | VARCHAR(512) | NULL | 团队头像（MinIO ossId 或外链） |
| creator_id | UUID | NOT NULL, FK → users.id | 创建人，自动成为团队创建者 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` 已解散 |
| disbanded_at | TIMESTAMPTZ | NULL | 解散时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`creator_id`)、INDEX(`status`)

### `team_members` — 团队成员表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| team_id | UUID | NOT NULL, FK → teams.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `exited` 主动退出 / `kicked` 被踢出 |
| joined_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 入队时间 |
| left_at | TIMESTAMPTZ | NULL | 离开时间 |

索引：

- PARTIAL UNIQUE(`team_id`, `user_id`) WHERE `status = 'active'`
- INDEX(`user_id`)

> 本表仅记录成员身份与入 / 退队状态；团队角色在 `user_roles` 中按 `scope='team'` + `object_id=本行 team_id` 查询。

### `team_member_applications` — 团队加入申请表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| team_id | UUID | NOT NULL, FK → teams.id | |
| user_id | UUID | NOT NULL, FK → users.id | 申请人 |
| invite_token | VARCHAR(64) | NULL | 使用的邀请链接令牌（数据存 Redis，仅记录使用来源） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'pending' | `pending` / `approved` / `rejected` |
| applied_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| reviewed_by | UUID | NULL, FK → users.id | 审批人 |
| reviewed_at | TIMESTAMPTZ | NULL | 审批时间 |

索引：

- PARTIAL UNIQUE(`team_id`, `user_id`) WHERE `status = 'pending'`
- INDEX(`user_id`, `status`)

### 团队角色授权（`user_roles`，scope='team'）

| 角色 code | 说明 |
| --- | --- |
| `team_creator` | 创建者（创建团队时自动授权） |
| `team_admin` | 团队管理员（分配 / 取消即增删授权） |
| `team_member` | 团队成员（审批通过时授权） |

- 授权记录：`scope='team'`、`object_id=<team_id>`、`role_id` 指向 `roles`（team 作用域）
- 成员退出 / 被踢出 / 团队解散时同步删除对应授权

## 数据所有权

- 团队资源（题目 / 题单 / 比赛 / 成员）仅在团队上下文可访问：查询必须带 `WHERE team_id = ?`
- 团队角色仅在 `scope='team'` 且 `object_id=<team_id>` 时生效；创建者 `team_creator` 权限集 ⊇ `team_admin`
- 用户只能查看自己所在团队的比赛 / 题单 / 团队题库（见各模块契约的可见性）
- 团队解散为软解散：`status='disbanded'`，同步清理 `user_roles`（scope='team'）授权与成员状态

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /teams | admin/tutor | 创建团队 | name, description? | team |
| GET | /teams/mine | auth | 我的团队列表（在册成员；带成员数与我的角色；与 /contests/me 同款资源域内 me 端点） | 分页/keyword（名称模糊） | team[] |
| GET | /teams/{id} | auth（成员） | 团队详情 | - | team |
| GET | /teams/{id}/members | team 角色 | 成员列表 | 分页/状态 | member[] |
| POST | /teams/{id}/invites | team_creator/team_admin | 生成邀请链接（写 Redis） | - | {token, expires_at} |
| GET | /teams/invites/{token} | public | 解析邀请链接（返回团队与有效期） | - | {team_id, team_name, expires_at} |
| POST | /teams/{id}/applications | auth | 提交加入申请 | invite_token | - |
| GET | /teams/{id}/applications | team_creator/team_admin | 申请列表 | 分页/状态 | application[] |
| POST | /teams/{id}/applications/{aid}/review | team_creator/team_admin | 审批（通过写 `user_roles` team_member） | approve, comment? | - |
| POST | /teams/{id}/members/{uid}/admin | team_creator/team_admin（仅创建者） | 分配 / 取消团队管理员 | is_admin | - |
| DELETE | /teams/{id}/members/{uid} | team_creator/team_admin | 踢出成员（清理授权） | - | - |
| POST | /teams/{id}/exit | auth（成员） | 主动退出（清理授权） | - | - |
| DELETE | /teams/{id} | team_creator/team_admin（仅创建者） | 解散团队 | - | - |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 团队不存在 / 邀请链接无效或已过期 |
| 2003 | 403 | 非团队创建者 / 管理员执行团队管理操作 |
| 3003 | 409 | 重复申请（已有 pending 申请） |
| 3002 | 409 | 邀请链接已过期 / 团队已解散 |

## 关键流程 / 验收条件

1. **创建团队**：`admin/tutor` 创建 → 自动写创建者 `team_members`（active）记录 + `user_roles` 授权 `team_creator`（scope='team'）。
2. **邀请链接**：`POST /teams/{id}/invites` 生成 token → 写 Redis `team:invite:<token>`（TTL=有效期，默认配置）；链接不可撤销、支持多人使用、无人数 / 一次性限制。用户经链接提交申请时记录 `invite_token` 来源。
3. **加入审批**：用户提交申请（pending）→ 创建者 / 管理员审批；通过 → 写 `team_members`（active）+ `user_roles`（`team_member`）+ 通知；拒绝 → 记录状态 + 通知（通知随通知模块开放，当前仅记录申请状态与审批人 / 时间）。
4. **分配管理员**：仅创建者可执行 `POST /teams/{id}/members/{uid}/admin`；分配即写 `team_admin` 授权，取消即删除。
5. **退出 / 踢出 / 解散**：同步清理成员记录状态与 `user_roles` 团队授权。

## 实现状态

- 已实现（迁移 0022）：团队基础能力端到端——创建（admin/tutor）/ 编辑信息 / 成员列表 /
  邀请链接生成与解析（Redis `team:invite:<token>`）/ 加入申请与审批 / 分配·取消管理员（仅创建者）/
  踢出 / 退出 / 解散（软解散，授权全清）；`GET /teams/mine` 我的团队列表。
- 已实现：为 `problem_sets.team_id` / `contests.team_id` 补 FK；`problems` 补 `team_id` 列 +
  FK + 索引，全站可见性 CHECK 扩展为契约双分支（全站 private/public，团队 admin_visible/team_visible）。
- 前端：`/teams/mine` 团队中心（列表 + 创建）、`/teams/:id` 详情工作台（成员 / 加入申请 / 设置三 tab，
  权限按 `my_role` 显隐）、`/teams/invites/:token` 邀请落地页（公开解析 + 申请加入）。
- 随 teams 模块开放（暂未实现）：团队题库 / 团队题单 / 团队比赛的业务功能
  （数据模型列与 FK 已就绪）；审批通知。

## 明确不做

- 邀请链接不设撤销、人数限制、一次性使用限制（按需求确定）
- 不单独建团队角色表 / 权限表（团队角色统一 `user_roles`，功能权限应用层分支）
- 团队解散后题目 / 题单 / 比赛默认归档，不物理删除
