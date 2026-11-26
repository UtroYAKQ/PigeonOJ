# 组织化改造计划稿

> 状态：**已实施**（2026-09-14 确认并落地，迁移 0039–0041；契约见 `docs/contracts/orgs.md` 及各模块契约修订）。实施调整：存量团队题目做破坏性清理（生产无重要数据）；团队题目引用来源放宽为「本组织组织题库 ∪ 全站公开题」；团队题单复制机制（copy_items_from）随个人出题取消一并移除。
> 背景：多组织共用一个 OJ 部署。现状模型以个人为中心（题目 `owner_id` 挂个人、`tutor` 全局角色、团队凭空创建），组织在数据模型中没有身份，被迫「一个组织共用一个导师账号」——带来会话互踢、冻结连坐、频控挤兑、审计失效、组织资产绑死账号等问题。本次改造把「组织」补进数据模型，作为内容和团队的所有者。

## 1. 目标模型

- **全局角色收敛为 `admin` / `user`**（单一角色、互斥不变）；**`tutor` 取消**
- **组织（organization）**：站点管理员创建组织，任命组织管理员；组织管理员拉人进组织
- **组织 = 导师组**：组织成员即出题人；学员不进组织，只进团队
- **组织题库**：题目归属组织，组织成员**全员可见、可编辑**（含草稿，无个人私稿）；创建人仅作署名（审计/展示）
- **团队挂在组织下**：团队不再直建题目，团队题目唯一来源 = **组织题库的快照引用**（沿用现有机制：`source_problem_id`、同团队同源唯一、统计从零累计、快照隔离、裸路径拦截）
- **跨团队复用**：同一组织题库题目可被组织内多个团队分别引用（「下个团队也可以用」成为正道）
- **外部团队管理员**：组织名下团队的 team_creator / team_admin 即使不是组织成员，也获得该组织题库的**只读**浏览权（供引用选题）
- **公开内容收归 admin**：全站题目 / 题单 / 比赛的创建权由 admin 承担（tutor 取消后的空缺）

### 角色总表（改造后）

| 作用域 | 角色 code | 说明 |
| --- | --- | --- |
| global | `admin` | 系统管理员（唯一内容兜底） |
| global | `user` | 普通用户（默认） |
| org | `org_admin` | 组织管理员：成员管理、组织信息、创建团队、授予/撤销组织管理员 |
| org | `org_member` | 组织成员：组织题库全量读写（创建/编辑/验题/发布/归档/交题） |
| team | `team_creator` / `team_admin` / `team_member` | 机制不变，团队挂在组织下 |

## 2. 决策点（草案默认取值，逐项可改）

| # | 决策 | 说明 / 备选 |
| --- | --- | --- |
| D1 | 组织角色只分两级 `org_admin` ⊇ `org_member` | 按「组织内都可见、可编辑」字面执行：`org_member` 即拥有题库全部编辑权（含他人草稿、验题发起）。备选：拆 `org_tutor`（可编辑）/ `org_member`（只读）——若将来学员也要进组织则必须拆 |
| D2 | 学员不进组织 | 组织成员=导师组；团队成员 ≠ 组织成员。团队管理员通常由组织成员担任，也允许外部人员（拉进团队即可），其只读可见组织题库 |
| D3 | 组织管理员自治理 | `org_admin` 可授予/撤销其他成员的 `org_admin`，站点 admin 亦可；约束：**至少保留一名 org_admin**（最后一名不可撤销/移出，新错误码 3004） |
| D4 | 解散权在站点 admin | 组织解散仅 admin 可执行；软解散 + 清理 org 授权 + 题库归档（对齐团队解散语义） |
| D5 | 组织加入 = 直接拉人 | 仅 `org_admin` 直接添加成员（支持批量），**不做**邀请链接/申请审批（v1 明确不做，后续可加） |
| D6 | 公开内容空缺归 admin | 全站题/题单/比赛创建门 `admin/tutor` → `admin`；组织题库题目不进题库中心（如需对外开放，将来加「发布到题库中心」，本期不做） |
| D7 | 存量 tutor 迁移 | 全局授权移除（降为 `user`）；原 tutor 名下个人题目由 admin 经**一次性划转脚本**批量设置 `org_id`（`owner_id` 保留署名）；未划转的全站题归 admin 管 |
| D8 | 存量团队兼容 | `teams.org_id` 可空；NULL 团队现有资源可用但**不可新增题目**（无组织题库来源）；admin 端点可逐个指派归属 |
| D9 | 团队编排候选调整 | 团队题单/比赛候选 = 本团队题目 ∪ 全站公开；移除「本人私有」（个人出题取消），组织题目须先引用进团队才能编排（保持快照边界） |
| D10 | 组织题目复用题库统一端点 | `/problems/{id}/...` 管理端点权限门扩展（org 题目门 = 组织成员），组织工作台只提供组织维度**列表/创建**入口；不为组织题库复制一整套管理端点。对比：团队空间选独立端点是因为学员封闭上下文，组织内全员可编辑无此需求。组织成员可对组织题交题/自测（统计归源题，团队快照口径不受影响） |

## 3. 数据模型变更

### `organizations` — 新表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL, UNIQUE | 组织名称 |
| description | TEXT | NULL | |
| avatar_url | VARCHAR(512) | NULL | 同 teams 头像规则（站内文件 URL 或可信外链） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` 已解散 |
| created_by | UUID | NOT NULL, FK → users.id | 创建操作人（站点 admin），仅审计署名、无权限语义 |
| disbanded_at | TIMESTAMPTZ | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`name`)、INDEX(`status`)

### `org_members` — 新表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| org_id | UUID | NOT NULL, FK → organizations.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `removed` 被移出 |
| added_by | UUID | NULL, FK → users.id | 拉人操作人 |
| joined_at / left_at | TIMESTAMPTZ | NOT NULL DEFAULT now() / NULL | |
| note | VARCHAR(64) | NULL | 成员备注（对齐团队备注语义） |

索引：PARTIAL UNIQUE(`org_id`, `user_id`) WHERE `status='active'`、INDEX(`user_id`)

### 既有表变更

| 表 | 变更 | 说明 |
| --- | --- | --- |
| `user_roles` | scope CHECK 扩展 `'org'` | `scope='org'`、`object_id=<org_id>`；角色经 `roles` 种子（新增 `org_admin` / `org_member`，scope='org'） |
| `roles` | 种子增删 | 新增 org 两角色；**移除 `tutor` 种子**（阶段 4 执行） |
| `teams` | + `org_id` UUID NULL, FK → organizations.id + INDEX(`org_id`) | 新建团队必填（经组织端点创建）；存量可空（D8） |
| `problems` | + `org_id` UUID NULL, FK → organizations.id + INDEX(`org_id`, `status`)；visibility CHECK 扩展 | org 题目分支：`org_id` 非空 ⇒ `visibility='org_visible'`；`org_id` 与 `team_id` 互斥（CHECK 兜底不同时非空）；`owner_id` 保留为创建人署名 |

## 4. 权限模型变更（同步 `docs/security.md`）

- 角色表：移除 `tutor`；新增 `org_admin` / `org_member`；单一全局角色模型不变（admin/user 互斥）
- 单一所有权模型修订：**全站资源**仍按 owner 判定（仅 admin 可管全站）；**组织题库**按组织成员资格判定（成员全员可管，`owner_id` 仅署名）；**团队资源**判定不变
- 权限矩阵关键变化：

| 功能 | user | admin | org_admin | org_member | team_creator/admin |
| --- | --- | --- | --- | --- | --- |
| 创建组织 | 否 | 是 | 否 | 否 | 否 |
| 组织成员管理（拉人/移出/授管理员） | 否 | 是 | 是（本组织） | 否 | 否 |
| 创建团队 | 否 | 是 | 是（本组织内） | 否 | 否 |
| 组织题库读 | 否 | 是 | 是 | 是 | 只读（本组织名下团队的管理员） |
| 组织题库写 | 否 | 是 | 是 | 是 | 否 |
| 创建全站题目/题单/比赛 | 否 | 是 | 否 | 否 | 否 |
| 团队题库引用（来自组织题库） | 否 | 是 | 是 | 是 | 是（机制不变） |

## 5. API 变更清单

### 新增 — 组织空间（前缀 `/api/v1`）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | /orgs | admin | 创建组织（name 唯一；创建者自动成为 org_admin；admin_user_ids[] 可另任命初始组织管理员） |
| GET | /orgs/mine | auth | 我加入的组织（带 my_role、成员数/团队数） |
| GET | /orgs/{id} | org 角色 | 组织详情（非成员 2003） |
| PUT | /orgs/{id} | org_admin | 编辑信息（name/description/avatar_url） |
| DELETE | /orgs/{id} | admin | 解散组织（软解散） |
| GET | /orgs/{id}/members | org 角色 | 成员列表（分页/keyword） |
| POST | /orgs/{id}/members | org_admin | 直接添加成员（user_ids[] 可批量；已在册跳过） |
| DELETE | /orgs/{id}/members/{uid} | org_admin | 移出成员（同步清 org 授权；最后一名 org_admin 3004） |
| PUT | /orgs/{id}/members/{uid}/admin | org_admin / admin | 授予/撤销组织管理员（is_admin；最后一名 3004） |
| PUT | /orgs/{id}/members/{uid}/note | 本人 或 org_admin | 成员备注（对齐团队） |
| POST | /orgs/{id}/teams | org_admin | 创建团队（org_id 固定；创建者自动 team_creator；visibility 缺省 private） |
| GET | /orgs/{id}/teams | org 角色 | 组织名下团队列表（带成员数/状态） |
| GET | /orgs/{id}/problems | org 角色 | 组织题库列表（status 过滤：缺省 published、`draft`=草稿视图全员可见、归档不返回；带 needs_reverification） |
| POST | /orgs/{id}/problems | org_member | 组织题库直建（visibility 恒 `org_visible`，owner_id=创建人署名） |

### 新增 — 管理后台

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /admin/orgs | admin | 组织全量列表（含解散；分页/keyword/status） |
| GET | /admin/orgs/{id} | admin | 组织详情（成员/团队/题库只读浏览，不做维护动作） |
| PUT | /admin/teams/{id}/org | admin | 存量团队指派组织（D8 迁移用） |

### 修改

| 模块 | 变更 |
| --- | --- |
| problems.md | `/problems/{id}/...` 管理端点权限门扩展：题目 `org_id` 非空时，读门 = org_member ∪（该组织名下团队的 team_creator/team_admin）∪ admin，写门 = org_member ∪ admin；`POST /problems` 收敛为 admin（全站题），**移除 team_id 直建分支**；`GET /problems` 的 `scope=mine` 语义改为：admin 全量 / 普通用户 = 所在组织的组织题聚合（多组织取并集）；`ownership` 过滤扩展 `org` 来源 |
| teams.md | 全局 `POST /teams` 移除（创建走 `/orgs/{id}/teams`）；`POST /teams/{team_id}/problems/references` 来源改为**本团队所属组织的题库**（已发布，不再要求「本人创建」）；`referenceable` 候选重定义 = 本组织题库已发布且未被该团队引用；其余团队机制（邀请链接/申请审批/成员管理/团队题单/团队比赛/快照语义）完全不变 |
| problem-sets.md | 全站题单创建/编辑/编排/下线权限门 `admin/tutor` → `admin`；团队题单编排候选调整（D9） |
| contests.md | 全站公开赛创建/编辑门 `admin/tutor` → `admin`；`/contests/{id}/problems/search` 同步；团队比赛编排候选调整（D9） |
| admin.md | 新增组织管理端点；`PUT /admin/users/{id}/roles` 全局角色枚举收敛为 `admin` / `user`；管理视图（题库/题单/比赛）中 tutor 相关口径移除 |

### 移除

- 全局 `tutor` 角色及其全部权限门（收敛为 admin 或组织门）
- `POST /problems` 的 `team_id` 团队直建分支

### 错误码

| 错误码 | HTTP | 说明 | 记录位置 |
| --- | --- | --- | --- |
| 3004 `ORG_LAST_ADMIN` | 409 | 组织最后一名管理员不可撤销/移出 | orgs.md（新契约文件） |
| 3001 / 3003 / 2003 / 1001 | — | 复用：组织不存在 / 组织名重复·重复添加成员 / 非组织管理员·非成员 / 参数错误 | 通用或 orgs.md |

## 6. 存量数据迁移（一次性，阶段 4 执行）

1. Alembic 迁移：新表 + 列 + CHECK 扩展（up/down 齐备）
2. 角色迁移：`roles` 种子增 org 两角色、删 `tutor`；存量 `user_roles`（scope='global', tutor）行删除 → 用户降为 `user`
3. 题目划转脚本（admin 交互执行）：按映射表把原 tutor 个人题目批量设置 `org_id`（`owner_id` 保留署名）；未划转的全站题保持 admin 管理
4. 存量团队指派：admin 经 `PUT /admin/teams/{id}/org` 逐个指派（或脚本批量）
5. 存量团队直建题（`team_id` 非空且 `referenced_at` NULL）保留原状，不强制改造

## 7. 分期实施

| 阶段 | 范围 | 验收要点 |
| --- | --- | --- |
| 1. 组织实体与角色 | `organizations` / `org_members` / scope='org' / roles 种子（tutor 暂不动）/ 组织端点 / 管理后台组织页 / `teams.org_id`（新建团队走组织端点，全局 `POST /teams` 关闭） | 创建组织→任命管理员→拉人→建团队端到端；非成员 2003；最后一名管理员保护；存量团队不受影响 |
| 2. 组织题库 | `problems.org_id` / `org_visible` 分支 / 统一端点权限门扩展 / 组织题库列表与创建 / 前端组织题库 tab | 成员可建题、编辑他人题、验题、发布；组织名下团队管理员只读可见；团队快照与全站题行为不变 |
| 3. 团队引用改造 | references 来源=组织题库 / referenceable 重定义 / 直建移除 / 编排候选调整（D9）/ 前端引用页与创建入口 | 同组织题目可引用进多个团队（快照、统计从零、防重不变）；外部团队管理员可引用；未引用的组织题不进团队编排 |
| 4. tutor 下线与存量迁移 | 角色种子/授权迁移、公开创建权收归 admin、划转脚本、`scope=mine` 语义切换、前端导师身份清理、全量文档同步 | tutor 不复存在；划转后组织题库→团队引用端到端回归；`check_import_rules` + 相关 pytest 通过 |

## 8. 前端影响（对齐 `docs/frontend.md`）

- **新增**：组织中心（我的组织）、组织工作台（信息 / 成员 / 团队 / 题库 tab，复用团队工作台的 tab + SearchFilterBar + 权限显隐模式）、管理后台组织管理页
- **调整**：团队创建入口（管理后台 → 组织工作台）、题库创建向导（组织上下文路由）、团队引用页候选来源、团队题库管理视图、题库中心 `scope=mine` 语义、全局导师身份相关 UI 清理
- **不变**：团队中心 / 邀请落地页 / 团队空间各上下文路由（学员侧无感）

## 9. 风险与兼容

- 未指派 `org_id` 的存量团队功能空窗（不可新增题目，只读存量）——须 admin 尽快完成指派
- 组织题库全员可编辑 → 并发编辑为最后写入胜（现状团队题面编辑亦无行锁，不新增机制）
- `org_id` 与 `team_id` 互斥、visibility 三分支由 CHECK 兜底，防脏数据
- 验题邀请机制不变（存在 pending 记录时任何登录用户可提交验题），组织题库直接沿用
- 快照引用机制完全复用：统计口径、同团队同源唯一、快照隔离、裸路径拦截均不回归

## 10. 文档同步清单（实施时）

| 文件 | 动作 |
| --- | --- |
| `docs/contracts/orgs.md` | 新增（组织模块契约） |
| `docs/contracts/index.md` | 模块表 + 领域关系图加组织 |
| `docs/contracts/teams.md` / `problems.md` / `problem-sets.md` / `contests.md` / `admin.md` | 按「API 变更清单」修订 |
| `docs/security.md` | 角色表、所有权模型、权限矩阵 |
| `docs/architecture.md` | 领域约定（组织/团队/题库关系） |
| `docs/workflow.md` | 映射表如需（新增契约文件行已在 index 流程内） |
