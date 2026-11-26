# 组织模块契约

> 组织、组织成员、组织题库。组织是多机构共用一个 OJ 的租户单元：站点管理员创建组织并任命组织管理员，组织管理员拉人、创建团队、维护组织题库；团队挂在组织下，团队题目只来自组织题库的快照引用（见 `teams.md`）。组织角色经 `user_roles`（`scope='org'`、`object_id=<org_id>`）统一授权，见 `docs/security.md`。

## 数据模型

### `organizations` — 组织表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL, UNIQUE | 组织名称（全站唯一） |
| description | TEXT | NULL | 组织简介 |
| avatar_url | VARCHAR(512) | NULL | 组织头像：站内完整文件 URL 或可信外链（同 teams 规则） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` 已解散 |
| created_by | UUID | NOT NULL, FK → users.id | 创建操作人（站点 admin），仅审计署名、无权限语义 |
| disbanded_at | TIMESTAMPTZ | NULL | 解散时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`name`)、INDEX(`status`)

### `org_members` — 组织成员表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| org_id | UUID | NOT NULL, FK → organizations.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `removed` 被移出 |
| added_by | UUID | NULL, FK → users.id | 拉人操作人 |
| joined_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 加入时间 |
| left_at | TIMESTAMPTZ | NULL | 移出时间 |
| note | VARCHAR(64) | NULL | 成员备注：本人可备注自己，org_admin 可备注任意成员；无权限语义 |

索引：

- PARTIAL UNIQUE(`org_id`, `user_id`) WHERE `status = 'active'`
- INDEX(`user_id`)

### 组织角色授权（`user_roles`，scope='org'）

| 角色 code | 说明 |
| --- | --- |
| `org_admin` | 组织管理员：成员管理（拉人 / 移出 / 授予·撤销 org_admin）、组织信息编辑、组织内创建团队 |
| `org_member` | 组织成员：组织题库全量读写（创建 / 编辑 / 验题 / 发布 / 归档 / 交题 / 自测） |

- 授权记录：`scope='org'`、`object_id=<org_id>`、`role_id` 指向 `roles`（org 作用域）
- `org_admin` 权限集 ⊇ `org_member`；一个用户可加入多个组织、在不同组织持不同角色
- 成员被移出 / 组织解散时同步删除对应授权；站点 admin 视同拥有全部组织管理权

## 数据所有权（组织题库）

- **组织是内容的所有者**：组织题库题目的管理权按组织成员资格判定，不按创建人判定；`problems.owner_id` 保留为创建人署名（审计/展示），在组织题目上无权限语义
- 组织题库对全体成员开放读写（含草稿）：无个人私稿，草稿箱视图为全组织草稿
- 组织题库为封闭上下文：仅组织成员经组织端点访问；组织名下团队的 team_creator / team_admin 额外获得**只读**浏览权（引用候选），见 `teams.md`
- 组织题目不进题库中心、不得编入全站题单 / 公开比赛；跨组织不互通
- 组织成员可对组织题交题 / 自测（统计归源题；团队快照口径不受影响）
- 组织解散为软解散：`status='disbanded'`，同步清理 `user_roles`（scope='org'）与成员状态；题库题目默认归档；**名下团队级联软解散**（对齐团队软解散语义，避免 `teams.org_id` 悬挂在已解散组织上无人治理）

## 端点

统一前缀 `/api/v1`。

### 组织空间

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /orgs | admin | 创建组织（name 全站唯一；创建者自动成为组织管理员，可另任命初始组织管理员） | name, description?, avatar_url?, admin_user_ids[] | org |
| GET | /orgs/mine | auth | 我加入的组织列表（active；带 my_role / 成员数 / 团队数） | 分页/keyword | org[] |
| GET | /orgs/{id} | org 角色 | 组织详情（非成员 2003） | - | org |
| PUT | /orgs/{id} | org_admin | 编辑组织信息 | name?/description?/avatar_url? | org |
| DELETE | /orgs/{id} | admin | 解散组织（软解散；清理 org 授权与成员状态，题库题目归档，名下团队级联软解散） | - | - |
| GET | /orgs/{id}/members | org 角色 | 成员列表 | 分页/keyword（昵称模糊） | member[] |
| POST | /orgs/{id}/members | org_admin | 直接添加成员（可批量；已在册跳过） | user_ids[] | - |
| DELETE | /orgs/{id}/members/{uid} | org_admin | 移出成员（同步清授权；最后一名 org_admin 3004，最后一名成员 3005） | - | - |
| PUT | /orgs/{id}/members/{uid}/admin | org_admin / admin | 授予 / 撤销组织管理员（最后一名 3004；org_admin 不可撤销自己，需其他管理员或站点 admin 代执行） | is_admin | - |
| PUT | /orgs/{id}/members/{uid}/note | 本人 或 org_admin | 设置成员备注（≤64 字符；空串 = 清除） | note | - |
| POST | /orgs/{id}/teams | org_admin | 创建团队（`teams.org_id` 固定为本组织；创建者自动 team_creator；visibility 缺省 private） | team 创建载荷 | team |
| GET | /orgs/{id}/teams | org 角色 | 组织名下团队列表（带成员数 / 状态 / my_role） | 分页/keyword/status | team[] |
| GET | /orgs/{id}/problems | org 角色 | 组织题库列表：缺省 published；`status='draft'` 草稿视图（全组织草稿，均可见可编辑）；归档任何视图不返回；列表项带 `needs_reverification` / 统计计数 | 分页/keyword/status | problem[] |
| POST | /orgs/{id}/problems | org_member | 组织题库直建题目（`visibility` 恒 `org_visible`，`owner_id` = 创建人署名；`referenced_at` 恒 NULL） | 题目创建载荷 | problem |
| GET | /orgs/{id}/problems/{pid} | org 角色 | 组织题目详情（组织上下文统一入口，复用题库详情装配） | - | problem |

### 组织题库管理动作（复用题库统一端点，权限门扩展）

组织题目（`problems.org_id` 非空）的管理动作不设独立端点，复用 `/problems/{id}/...`
统一端点，权限门按归属扩展（见 `problems.md`）：

- 读门（详情 / 测试点读取 / 自测）：org_member ∪（该组织名下团队的 team_creator / team_admin）∪ admin
- 写门（题面 / 测试点 / 样例 / SPJ / 验题发起 / 发布 / 归档）：org_member ∪ admin
- 验题邀请机制不变（存在 pending 记录时任何登录用户可提交验题）

### 管理端视图（admin）

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /admin/orgs | admin | 组织管理列表：全量（含已解散），创建时间倒序；带成员数 / 团队数 / 状态 | 分页/keyword（名称模糊）/status | org[] |
| GET | /admin/orgs/{id} | admin | 组织管理详情（免成员校验，含已解散） | - | org（含成员 / 团队 / 题库只读浏览） |
| PUT | /admin/teams/{id}/org | admin | 存量团队指派组织（迁移用；org 必须为 active） | org_id | team |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3004 `ORG_LAST_ADMIN` | 409 | 组织最后一名管理员不可撤销 / 移出 |
| 3005 `ORG_LAST_MEMBER` | 409 | 组织最后一名成员不可移出 |
| 3001 | 404 | 组织不存在 |
| 3003 | 409 | 组织名已存在 / 重复添加成员 |
| 2003 | 403 | 非组织管理员执行管理操作；非成员访问组织空间；org_admin 撤销自己的管理员身份 |
| 1001 | 400 | 参数格式错误（名称长度、非法状态值等） |

## 关键流程 / 验收条件

1. **创建组织**：站点 admin `POST /orgs` → 写 `organizations` + 创建者自动成为组织管理员（写 `org_members` + `org_admin` 授权，即使未在 `admin_user_ids` 列出）再批量写其他初始管理员；创建者可在「我的组织」看到该组织。
2. **拉人**：org_admin `POST /orgs/{id}/members` → 写 `org_members`；被拉人即时获得组织题库读写权（org_member）。
3. **授管理员**：`PUT /orgs/{id}/members/{uid}/admin` 授予即写 `org_admin` 授权、撤销即删（最后一名拒绝 3004）；站点 admin 可对任意成员执行。**自我撤销保护**：org_admin 不可撤销自己的管理员身份（返回 2003），避免误操作后失去管理权；需由其他组织管理员或站点 admin 代执行，与团队「创建者保护」同语义。
4. **移出**：删除 `org_members` active 行（置 removed）+ 清理该用户在本组织的全部授权；最后一名 org_admin 拒绝 3004、最后一名成员拒绝 3005。
5. **创建团队**：org_admin `POST /orgs/{id}/teams` → 团队 `org_id` 落本组织，创建者自动 `team_creator`（复用 teams 模块语义）；团队邀请 / 申请 / 成员管理机制不变。
6. **组织题库生命周期**：org_member 直建（草稿）→ 编辑题面 / 测试点（复用题库端点，组织门）→ 验题 → 发布 → 可被组织内团队引用（快照复制，见 `teams.md`）；归档退出列表。
7. **解散**：仅站点 admin；软解散，题库题目归档、名下团队级联软解散、org / team 授权全清。

## 实现状态

- 契约先行；实现随「组织化改造」落地（迁移 0039 起）。
- 已实现：组织实体 / 成员 / scope='org' 角色 / 组织空间端点 / 管理端视图 / 组织题库 / 团队引用来源切换 / tutor 下线。
- 已实现（组织题目作答动线）：组织题库列表行点击已发布题进入组织作答页
  （`/me/orgs/:orgId/problems/:pid`，复用题库详情组件，读 / 交题 / 自测走题库裸路径端点，
  组织成员经 can_manage 放行），草稿行点击仍进编辑向导；行内 ⋯ 下拉保留「编辑」入口。
- 存量处理（破坏性，生产无重要数据）：原团队题目及其提交 / 测试点等从属数据在迁移中直接删除；存量团队 `org_id` 为空，由 admin 指派后方可引用题目。
- 暂未实现：组织题库发布到题库中心（明确不做，见下）。

## 明确不做

- 组织不做邀请链接 / 加入申请审批（org_admin 直接拉人；后续有需要再加）
- 不单独建组织角色表 / 权限表（组织角色统一 `user_roles`，功能权限应用层分支）
- 组织题库不进题库中心（对外开放将来以「发布到题库中心」独立设计）
- 跨组织题目不互通（无共享开关）
- 组织级题单 / 比赛（题单 / 比赛仍收敛在团队与全站两层）
