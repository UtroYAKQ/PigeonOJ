# 团队模块契约

> 团队、成员、加入申请与邀请链接。团队角色经 `user_roles`（`scope='team'`、`object_id=<team_id>`）统一授权，见 `docs/security.md`。

## 数据模型

### `teams` — 团队表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL | 团队名称 |
| description | TEXT | NULL | 团队简介 |
| avatar_url | VARCHAR(512) | NULL | 团队头像：站内完整文件 URL（`/api/v1/files/users/{uid}/images/{uuid}`，即 `POST /files/upload/image` 返回的 `url`）或可信外链 `http(s)://…`；前端直接渲染 |
| creator_id | UUID | NOT NULL, FK → users.id | 创建人，自动成为团队创建者 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` 已解散 |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'private' | `public` 公开（团队中心可见、可直接申请加入）/ `private` 私有（不进团队中心，仅凭邀请链接申请） |
| disbanded_at | TIMESTAMPTZ | NULL | 解散时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`creator_id`)、INDEX(`status`)、INDEX(`visibility`, `status`)

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
| POST | /teams | admin/tutor | 创建团队（入口在管理后台 `/admin/teams`；自动写创建者成员记录 + team_creator 授权；visibility 缺省 private） | name, description?, avatar_url?, visibility? | team |
| GET | /teams | public / auth | 团队中心列表：仅 public + active 团队（创建时间倒序，匿名可看；在册成员带 my_role，非成员 my_role=null；**成员判定以 `team_members.active` 为唯一口径**，`user_roles` 角色行仅用于细化角色层级——角色残留不得令非成员带 my_role，避免卡片态与详情权限不一致挡住重新申请）；`mine=true`（「我的团队」勾选，须登录，匿名 401）改为本人在册团队（公开 + 私有）；前端非成员点卡片弹申请确认（详情仅成员可见） | 分页/keyword（名称模糊）/mine | team[]（TeamSummary，含 visibility / member_count / my_role） |
| GET | /teams/mine | auth | 我的团队列表（在册成员；带成员数与我的角色；与 /contests/me 同款资源域内 me 端点） | 分页/keyword（名称模糊） | team[] |
| GET | /teams/{id} | auth（成员） | 团队详情（非成员 2003；前端详情页对 2003 提供申请加入出口） | - | team |
| GET | /teams/{id}/members | team 角色 | 成员列表 | 分页/keyword（昵称模糊）/状态 | member[] |
| POST | /teams/{id}/invites | team_creator/team_admin | 生成邀请链接（写 Redis） | - | {token, expires_at} |
| GET | /teams/invites/{token} | public | 解析邀请链接（返回团队与有效期） | - | {team_id, team_name, avatar_url, expires_at} |
| POST | /teams/{id}/applications | auth | 提交加入申请（public 团队可直接申请；private 团队无 invite_token 返回 2003，凭有效邀请链接放行；invite_token 经私有团队申请时记录来源） | invite_token | - |
| GET | /teams/{id}/applications | team_creator/team_admin | 申请列表 | 分页/状态 | application[] |
| POST | /teams/{id}/applications/{aid}/review | team_creator/team_admin | 审批（通过写 `user_roles` team_member） | approve, comment? | - |
| POST | /teams/{id}/members/{uid}/admin | team_creator/team_admin（仅创建者） | 分配 / 取消团队管理员 | is_admin | - |
| DELETE | /teams/{id}/members/{uid} | team_creator/team_admin | 踢出成员（清理授权） | - | - |
| POST | /teams/{id}/exit | auth（成员） | 主动退出（清理授权） | - | - |
| DELETE | /teams/{id} | team_creator/team_admin（仅创建者） | 解散团队 | - | - |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 团队不存在 / 邀请链接无效或已过期 / 题目或题单不在该团队 |
| 2003 | 403 | 非团队创建者 / 管理员执行团队管理操作；非成员访问团队空间；私有团队未经邀请链接直接申请；引用非本人题目 / 复制非本人题单 |
| 3003 | 409 | 重复申请（已有 pending 申请） |
| 3002 | 409 | 邀请链接已过期 / 团队已解散 / 复制来源题单已下线 |
| 1001 | 400 | 团队题目被二次引用 / 编排含不可见题目 / 可见性非法 / 团队题单不可作为复制来源 |

## 关键流程 / 验收条件

1. **创建团队**：`admin/tutor` 创建 → 自动写创建者 `team_members`（active）记录 + `user_roles` 授权 `team_creator`（scope='team'）；`visibility` 缺省 private。
2. **可见性与加入入口**：`public` 团队出现在团队中心（`GET /teams`，匿名可看），登录用户可直接提交加入申请；`private` 团队不进团队中心，唯一申请入口为邀请链接（无 invite_token 返回 2003）。可见性切换由创建者 / 管理员经编辑动线（`PUT /teams/{id}`）进行，即时生效。
3. **邀请链接**：`POST /teams/{id}/invites` 生成 token → 写 Redis `team:invite:<token>`（TTL=有效期，默认配置）；链接不可撤销、支持多人使用、无人数 / 一次性限制。用户经链接提交申请时记录 `invite_token` 来源。
4. **加入审批**：用户提交申请（pending）→ 创建者 / 管理员审批；通过 → 写 `team_members`（active）+ `user_roles`（`team_member`）+ 通知；拒绝 → 记录状态 + 通知（通知随通知模块开放，当前仅记录申请状态与审批人 / 时间）。
5. **分配管理员**：仅创建者可执行 `POST /teams/{id}/members/{uid}/admin`；分配即写 `team_admin` 授权，取消即删除。
6. **退出 / 踢出 / 解散**：同步清理成员记录状态与 `user_roles` 团队授权。

## 团队空间（题库 / 题单 / 比赛，限界上下文）

团队空间对题目 / 题单 / 比赛的创建与编排使用**独立端点**（`/teams/{team_id}/...` 前缀），
与公开上下文（题库中心 / 题单中心 / 比赛中心）互相隔离：

- **团队题目 = 引用制（快照复制）+ 团队直建**：出题人在个人空间（题库）创作题目（全站 private），经
  `POST /teams/{team_id}/problems/references` 引用进团队——**快照复制新题**（0030 起，
  源题留在个人题库）：新题继承题面 / 样例 / 生效测试点（MinIO 对象复制）/ 标签 /
  验题与发布状态，归属团队、可见性转团队分支、`source_problem_id` 指向源题
  （同团队同源唯一，重复引用 3003）、`referenced_at` = 引用时间。**统计数据从零累计**
  ——团队通过率为纯团队口径，不混入源题引用前的个人提交。快照后两题独立演进
  （源题改动不跟随）；快照题题库裸路径一律拦截，访问 / 交题 / 自测只能走团队上下文端点。
  创建权限门为 team_creator / team_admin，且仅可引用**本人创建**的已发布题目
  （admin 全站同权）。另支持团队上下文**直建**：`POST /problems` 携带 `team_id`
  （须为该团队 team_creator / team_admin，visibility 落团队分支，`referenced_at` 恒 NULL），经题库创建向导的团队上下文路由完成
- **团队题单**：team_creator / team_admin 直接创建（`visibility='team'`），可选
  `copy_items_from` 复制本人全站题单的题目条目（**快照复制**：源题单保留在全站，
  两题单独立演进；`referenced_at` = 复制时间，仅作来源标记）；题单内编排候选 =
  已发布且（本团队题目 ∪ 全站公开 ∪ 本人私有）
- **团队比赛**：team_creator / team_admin 直接创建（`contest_type='team'`）；
  编排候选在公开比赛规则（全站公开 ∪ 本人私有）之上放开本团队题目；
  报名 / 看题 / 交题窗口复用比赛统一端点（团队比赛报名叠加团队成员校验）
- **可见性**：团队题目题库裸路径（`GET /problems/{id}` / 直提 / 自测）按可见性严格拦截，
  成员只能经团队上下文端点访问（上下文隔离）；团队题单 / 团队比赛详情复用题单 /
  比赛模块统一端点（团队成员放行，非成员 2003）
- **隔离**：团队题目不得编入全站题单 / 公开比赛（编排候选校验排除 `team_id` 非空的题目）；
  团队题单 / 团队比赛不出现在对应公开中心

### 团队空间端点

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /teams/{team_id}/problems | team 角色 | 团队题库列表：成员见 published+team_visible；创建者 / 管理员主列表仅见已发布（含 admin_visible，草稿收敛到 status='draft' 草稿箱视图且仅本人草稿、他人草稿不可见，归档在团队空间任何视图不返回）；管理视图列表项带 `needs_reverification`（存在待验证测试点或样例晚于最近验题通过时间）；列表项带 `referenced_at` 引用字段与通过率计数 / 作答状态 | 分页/keyword/visibility | problem[] |
| POST | /teams/{team_id}/problems/references | team_creator/team_admin | 引用本人全站题目进团队（单向；二次引用 1001、他人题目 2003、归档题 409 语义同题库） | problem_id, visibility（team_visible/admin_visible，默认 team_visible） | problem |
| GET | /teams/{team_id}/problems/referenceable | team_creator/team_admin | 团队题目引用候选搜索（引用页列表）：本人创建 + 已发布 + 全站题 + 未被该团队引用过（同团队同源仅一份快照，服务端排除已引用源题） | 分页/keyword | problem[] |
| GET | /teams/{team_id}/problems/arrangeable | team_creator/team_admin | 团队编排候选搜索（题单编排挑题）：已发布且（本团队题目 ∪ 全站公开 ∪ 本人私有） | 分页/keyword | problem[] |
| PUT | /teams/{team_id}/problems/{pid}/statement | team 角色（题目管理者） | 团队上下文编辑题面（编辑向导第一步）：成员门 + 归属校验后复用题库 update（owner/admin 强校验） | 题面编辑载荷 | problem |
| GET | /teams/{team_id}/problems/{pid} | team 角色 | 团队题目详情（统一入口）：归属校验 + 团队可见性门（admin_visible 仅团队管理）后复用题库详情装配 | - | problem |
| POST | /teams/{team_id}/problems/{pid}/submissions | team 角色 | 团队题库内交题（统一入口，`submit_type='practice'`）：门控通过后豁免题库可见性，走统一判题链路 | language/code | submission_id |
| POST | /teams/{team_id}/problems/{pid}/run-code | team 角色 | 团队题库内用户自测：门控复用详情端点，豁免题库可见性后经网关派发 | language/code/input | self_test_result |
| GET | /teams/{team_id}/problem-sets | team 角色 | 团队题单列表（可见性与团队题目对齐）：成员仅见 team_visible 且未下线；创建者 / 管理员另见 admin_visible；status 显式传入按值过滤（团队管理视图） | 分页/keyword/status | problem_set[]（含 item_count / referenced_at / visibility） |
| GET | /teams/{team_id}/problem-sets/{set_id} | team 角色 | 团队题单详情（团队上下文统一入口，不走 /problem-sets/{id}）：成员门 + 归属校验 + 可见性门（admin_visible 仅团队管理）后复用题单详情装配 | - | problem_set（含 items / can_manage / owner_name / visibility） |
| GET | /teams/{team_id}/problem-sets/{set_id}/problems/{pid} | team 角色 | 团队题单内题目详情（团队上下文统一入口）：归属校验（题目属于该题单）后复用题库详情装配 | - | problem |
| POST | /teams/{team_id}/problem-sets/{set_id}/problems/{pid}/submissions | team 角色 | 团队题单内交题（团队上下文统一入口）：归属校验后走统一判题链路 | language/code | submission_id |
| POST | /teams/{team_id}/problem-sets/{set_id}/problems/{pid}/run-code | team 角色 | 团队题单内用户自测：门控复用题目详情端点 | language/code/input | self_test_result |
| POST | /teams/{team_id}/problem-sets | team_creator/team_admin | 创建团队题单（visibility 与团队题目对齐：team_visible 全队可见（缺省）/ admin_visible 仅团队管理）；`copy_items_from` 非空 = 复制本人全站题单条目（快照复制，源题单保留；他人题单 2003、已下线 409、团队题单作来源 1001） | title/description?/visibility?/copy_items_from? | problem_set |
| PUT | /teams/{team_id}/problem-sets/{set_id}/items | team_creator/team_admin | 编排团队题单：候选 = 已发布且（本团队题目 ∪ 全站公开 ∪ 本人私有）；重复 3003 | items[{problem_id, sort_order}] | - |
| POST | /teams/{team_id}/problem-sets/{set_id}/archive | team_creator/team_admin | 下线团队题单（不做物理删除） | - | problem_set |
| GET | /teams/{team_id}/contests | team 角色 | 团队比赛列表：本团队全部状态比赛 | 分页/status/keyword | contest[] |
| POST | /teams/{team_id}/contests | team_creator/team_admin | 创建团队比赛（contest_type='team'）；编排候选放开本团队题目 | contest 创建载荷 | contest |
| GET | /teams/{team_id}/contests/{cid} | team 角色 | 团队比赛详情（团队上下文统一入口）：成员门 + 归属校验后复用比赛详情装配 | - | contest |
| PUT | /teams/{team_id}/contests/{cid} | team_creator/team_admin | 编辑团队比赛 | contest 编辑载荷 | contest |
| POST | /teams/{team_id}/contests/{cid}/register | team 角色 | 团队比赛报名 | - | - |
| GET | /teams/{team_id}/contests/{cid}/problems | team 角色 | 团队比赛题目列表 | - | contest_problem[] |
| GET | /teams/{team_id}/contests/{cid}/problems/search | team_creator/team_admin | 团队比赛编排候选搜索 | 分页/keyword | problem[] |
| GET | /teams/{team_id}/contests/{cid}/problems/{pid} | team 角色 | 团队比赛内题目详情 | - | problem |
| POST | /teams/{team_id}/contests/{cid}/problems/{pid}/submissions | team 角色 | 团队比赛内交题 | language/code | submission_id |
| GET | /teams/{team_id}/contests/{cid}/board | team 角色 | 团队比赛榜单 | - | board |
| GET | /teams/{team_id}/contests/{cid}/board/{uid}/{pid}/accepted | team 角色 | 榜单单格 AC 提交 | - | submission[] |
| GET | /teams/{team_id}/contests/{cid}/submissions | team 角色 | 团队比赛提交记录 | 分页/筛选 | submission[] |
| GET | /teams/{team_id}/contests/{cid}/submissions/{sid} | team 角色 | 团队比赛提交详情 | - | submission |
| POST | /teams/{team_id}/contests/{cid}/unfreeze | team_creator/team_admin | 解冻榜单 | - | contest |
| PUT | /teams/{team_id}/contests/{cid}/announcement | team_creator/team_admin | 更新公告 | announcement | contest |
| POST | /teams/{team_id}/contests/{cid}/extend | team_creator/team_admin | 赛时延时 | end_time | contest |
| PUT | /teams/{team_id}/contests/{cid}/freeze-time | team_creator/team_admin | 调整封榜时间 | freeze_time | contest |
| GET | /teams/{team_id}/contests/{cid}/scoreboard-show | team_creator/team_admin | 滚榜数据 | - | scoreboard_show |

> 团队比赛详情 / 报名 / 榜单 / 交题 **必须**走上表团队端点（成员门 + 比赛归属该团队）；
> 全站 `GET /contests/{id}` 对团队比赛仍对团队成员放行（非成员 2003），供管理端只读浏览。
> **前端路由限界上下文**：团队比赛以 `/teams/:teamId/contests/:cid` 系列路由呈现
> （详情 / 内题目 / 内评测结果），面包屑挂在团队层级，内部导航不跳出团队前缀；
> 数据端点走本表团队比赛端点。
> 团队题目与团队**题单**详情 / 交题 / 自测同样必须走上表团队端点
> （题单统一入口 / 题库裸路径严格拦截，限界上下文隔离）。

### 管理端视图（admin，只读浏览）

管理后台（`/admin/teams`）对团队做全量只读浏览，免团队角色校验（admin 全局角色门）；
团队内容的维护（编辑信息 / 邀请 / 审批 / 踢出 / 编排）仍收敛在团队空间端点
（创建者 / 团队管理员），管理端不提供维护动作。**创建团队入口收敛在管理后台**
（前端 `/admin/teams` 页面提供创建按钮；`POST /teams` 权限不变，仍为 admin/tutor）。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /admin/teams | admin | 团队管理列表：全量（含已解散），创建时间倒序；带成员数 / 创建人昵称 / 状态 | 分页/keyword（名称模糊）/status | team[]（TeamAdminSummary：TeamSummary + status + creator_nickname） |
| GET | /admin/teams/{id} | admin | 团队管理详情（免成员校验，含已解散） | - | team（TeamAdminDetail：TeamDetail + creator_nickname） |
| GET | /admin/teams/{id}/members | admin | 成员列表（status 缺省 = 在册） | 分页/keyword（昵称模糊）/状态 | member[] |
| GET | /admin/teams/{id}/problems | admin | 团队题库列表（全部状态 / 可见性，含草稿与归档） | 分页/keyword/status/visibility | problem[] |
| GET | /admin/teams/{id}/problem-sets | admin | 团队题单列表（含已下线） | 分页/keyword/status | problem_set[] |
| GET | /admin/teams/{id}/contests | admin | 团队比赛列表（全部状态） | 分页/keyword/status | contest[] |

### 引用字段（referenced_at / source_problem_id）

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `problems` | `referenced_at` TIMESTAMPTZ NULL | 非空 = 经团队引用进入团队题库（引用时间，快照复制新题）；题库直建 / 团队直建 / 全站题目恒 NULL |
| `problems` | `source_problem_id` UUID NULL, FK → problems.id | 引用快照的源题（同团队同源唯一索引兜底防重）；非引用产生恒 NULL |
| `problem_sets` | `referenced_at` TIMESTAMPTZ NULL | 非空 = 复制自本人全站题单的团队题单（复制时间，快照语义仅来源标记）；团队直建 / 全站题单恒 NULL |

团队题目引用为**快照复制**：新题统计数据（`problem_counters` / `submissions`）从零累计，
团队通过率为纯团队口径；源题与快照题各自独立演进。团队题单复制同为快照语义
（复制题目条目，源题单保留在全站）。

团队比赛为团队空间直接创建，无引用语义，不设引用字段。

## 实现状态

- 已实现（迁移 0032，团队题单可见性双分支）：`problem_sets` 团队分支 visibility
  对齐团队题目——'team' 更名 'team_visible'（存量回填，原语义即全队可见），
  新增 'admin_visible'（仅团队创建者 / 管理员可见：列表 / 详情 / 题单内题目 /
  交题 / 自测均对普通成员拦截）；创建团队题单可选可见性（缺省 team_visible）；
  题单中心 mine 勾选排除团队题单（封闭空间，后端兜底）。
  前端：团队题单创建页可见性单选、团队详情题单列表管理视图可见性列。
  题单管理（/admin/problem-sets）：列表项带 `team_id`，`ownership` 来源筛选
  （solo=全站题单 / team=团队题单），可见性列映射团队分支（团队可见 / 管理可见）。
- 已实现（迁移 0031，团队可见性）：`teams` 增 `visibility`（public / private，缺省 private，
  存量回填 private）；`GET /teams` 团队中心列表（仅 public+active，匿名可看，
  `mine=true` 「我的团队」勾选须登录）；私有团队申请须凭邀请链接（无 token 2003）；
  创建 / 编辑携带 visibility（编辑由 team_creator / team_admin 执行，切换即时生效）。
  前端：`/teams/mine` 团队中心（公开团队卡片墙 + 「我的团队」勾选；公开团队非成员
  卡片「申请加入」）、`/teams/:id` 团队设置抽屉增可见性切换、管理后台创建团队增可见性选择。
- 已实现（团队题库发布 / 草稿箱语义）：团队管理视图主列表仅返回已发布题目
  （草稿经 `status='draft'` 进入草稿箱视图且仅本人草稿；归档在团队空间任何视图
  不返回，管理后台 admin_view 仍可查全量）；管理视图回填 `needs_reverification`。
  前端 `/teams/:id` 团队题库 tab：管理视图带「发布与验题」「可见性」列，
  工具栏右侧「草稿箱」勾选项——勾选后列表切换为本人草稿题目（行点击进编辑向导）；
  成员视图不变（仅 published+team_visible，无状态列）。

- 已实现（0029 起，题单复制语义收敛）：团队题单取消「引用（归属切换）」端点
  （`POST /teams/{team_id}/problem-sets/references` 移除），改为创建时可选
  `copy_items_from` 快照复制本人全站题单条目（源题单保留在全站，`referenced_at`
  仅作来源标记）；存量归属切换产生的团队题单保留现状。
- 已实现（迁移 0029）：团队空间端到端——团队题库（引用 / 列表 / 详情 / 交题 / 自测）/
  团队题单（创建 / 编排 / 下线 / 详情复用题单端点）/ 团队比赛（创建 / 列表 /
  报名与看题窗口复用比赛端点）；`problems` / `problem_sets` 增 `referenced_at` 引用字段；
  编排候选隔离（团队题目不得流入全站编排）。
- 已实现（团队比赛上下文）：团队比赛详情 / 报名 / 题目 / 交题 / 榜单 / 提交记录 /
  提交详情 / 解冻 / 公告 / 滚榜独立端点（`/teams/{team_id}/contests/{cid}/...` 前缀），
  成员门 + 比赛归属该团队后复用比赛装配；前端团队比赛路由数据端点走本前缀。
- 已实现（团队题单上下文）：团队题单详情 / 题单内题目详情 / 题单内交题 / 题单内自测
  独立端点（`/teams/{team_id}/problem-sets/...` 前缀），不再复用题单统一入口
  （限界上下文隔离）；`POST /problems` 补 `team_id` 团队上下文直建
  （团队 creator/admin，visibility 落团队分支）。
- 已实现（迁移 0022）：团队基础能力端到端——创建（admin/tutor）/ 编辑信息 / 成员列表 /
  邀请链接生成与解析（Redis `team:invite:<token>`）/ 加入申请与审批 / 分配·取消管理员（仅创建者）/
  踢出 / 退出 / 解散（软解散，授权全清）；`GET /teams/mine` 我的团队列表。
- 已实现（0030，团队引用 = 快照复制）：引用生成新题继承题面 / 生效测试点（MinIO 对象
  复制）/ 标签 / 验题发布状态，`source_problem_id` 防重与追溯，统计从零累计（纯团队
  通过率口径）；快照题裸路径全拦截；存量归属切换产生的引用题保留现状。
- 已实现：为 `problem_sets.team_id` / `contests.team_id` 补 FK；`problems` 补 `team_id` 列 +
  FK + 索引，全站可见性 CHECK 扩展为契约双分支（全站 private/public，团队 admin_visible/team_visible）。
- 前端：`/teams/mine` 团队中心（公开团队列表卡片墙 + 右上角「我的团队」勾选切换
  在册团队；公开团队非成员卡片带「申请加入」，详情仅成员可进；创建入口已收敛到
  管理后台）、
  `/teams/:id` 详情工作台（成员 / 团队题库 / 团队题单 / 团队比赛 / 加入申请五 tab，
  各 tab 带 SearchFilterBar 搜索 + 刷新，权限按 `my_role` 显隐；团队题库管理视图
  带发布验题 / 可见性两列与「草稿箱」勾选项，主列表仅已发布）、`/teams/invites/:token`
  邀请落地页（公开解析 + 申请加入）、`/teams/:teamId/problems/:pid` 团队写题页
  （复用题库详情组件，详情 / 交题 / 自测 / 评测结果全部走团队上下文路由，不跳出）。
- 前端（团队题单上下文路由，限界上下文）：`/teams/:teamId/sets/:setId` 团队题单详情
  （复用题单详情组件按上下文取参）、`/teams/:teamId/sets/:setId/arrange` 编排页
  （与后台题单详情同款，候选走 arrangeable）、`/teams/:teamId/sets/:setId/problems/:pid` 团队题单内写题页、
  `/teams/:teamId/sets/:setId/problems/:pid/submissions/:sid` 评测结果——
  读 / 交题 / 自测全部走团队题单端点，与题单统一入口完全隔离。
- 前端（团队比赛上下文路由，限界上下文）：`/teams/:teamId/contests/:cid` 团队比赛详情、
  `/teams/:teamId/contests/:cid/edit/basic` 与 `/edit/problems` 编辑向导、
  `/teams/:teamId/contests/:cid/tools` 赛时工具、
  `/teams/:teamId/contests/:cid/problems/:pid` 内写题页、
  `/teams/:teamId/contests/:cid/problems/:pid/submissions/:sid` 与
  `/teams/:teamId/contests/:cid/submissions/:sid` 评测结果——路由与面包屑隔离在团队层级；
  数据端点走团队比赛上下文端点（见「团队空间端点」表）。
  团队比赛列表（创建者 / 管理员）行内「⋯」提供「赛前管理」（仅 `scheduled`）与「赛时工具」。
- 前端（团队创建页，模仿后台创建页形态）：`/teams/:teamId/sets/new` 题单创建页
  （单一表单：标题 + Markdown 说明 + 可选「从我的题单复制」下拉）、
  `/teams/:teamId/problems/new` 题目引用页（团队题目 = 引用制；候选走
  `referenceable` 端点，已引用源题不再出现在列表）、
  `/teams/:teamId/contests/new` 比赛创建页（精简表单，编排随后在比赛编辑页）。
  复制来源选择仅 tutor / admin 全局身份可见（复制要求本人创建的全站题单，
  后端另有 ownership 校验兜底）。
- 前端（管理后台）：`/admin/teams` 团队管理（全量列表 + 筛选 + 创建团队，admin），
  `/admin/teams/:id` 团队详情（团队信息卡 + 成员 / 团队题库 / 团队题单 / 团队比赛只读浏览，
  含已解散团队与草稿 / 归档 / 已下线资源；不做维护动作）。
- 暂未实现：审批通知。

## 明确不做

- 邀请链接不设撤销、人数限制、一次性使用限制（按需求确定）
- 不单独建团队角色表 / 权限表（团队角色统一 `user_roles`，功能权限应用层分支）
- 团队解散后题目 / 题单 / 比赛默认归档，不物理删除
