# 数据模型与 API 契约

> 全站唯一的接口 / 数据模型契约。改表结构、API、错误码、权限门之前读本文件。
> 表结构的**唯一事实来源**是 `src/backend/alembic/versions/` 下的迁移 SQL；本文件是其文档化说明，两者必须同步。

## 目录

1. [通用约定](#1-通用约定) — 信封、错误码、分页
2. [领域模型总览](#2-领域模型总览)
3. [跨域规则](#3-跨域规则) — 所有权、可见性、编排候选（只在此处定义）
4. [用户与认证](#4-用户与认证)
5. [组织](#5-组织)
6. [团队](#6-团队)
7. [题库](#7-题库)
8. [题单](#8-题单)
9. [比赛](#9-比赛)
10. [判题与沙箱](#10-判题与沙箱)
11. [社区](#11-社区)
12. [管理 / 运维](#12-管理--运维)
13. [附录：实现状态与明确不做](#13-附录实现状态与明确不做)

---

## 1. 通用约定

### 1.1 响应信封

统一前缀 `/api/v1`，统一信封 `{ code, message, data }`。

```json
{ "code": 0, "message": "ok", "data": { } }
```

- `code=0` 成功；非 0 失败，取值见错误码表（错误码不可为 0）
- 框架参数校验失败（FastAPI 422）由全局异常处理器转为 `1001` / HTTP 400 信封，不返回原生 `{"detail": [...]}`
- **message 语言协商**：业务代码统一抛中文，出口按 `Accept-Language`（`zh-CN` 默认 / `en-US`）经 `app/core/i18n.py` 翻译，未命中回退中文；`code` 不受语言影响。前端 `api/http.ts` 自动携带界面语言
- 未捕获异常统一兜底：`IntegrityError` → `3002`（409），未知异常 → `5000`（500，不回传内部细节）；禁止依赖 Starlette 默认纯文本 500

**实现约定**：信封与分页为泛型 Pydantic 契约（`ApiResponse[T]` / `PaginatedResponse[T]`）；路由以 `response_model` 声明返回类型（`model_dump` 禁止；错误信封仅由 `app/core/exceptions.py` 的 `error(...)` 产生）。

每条响应回传 `X-Request-Id`，与 `request_logs.request_id` 一一对应。

### 1.2 错误码

**通用码**（已有对应场景时优先复用，不新增）：

| 码 | HTTP | 说明 |
| --- | --- | --- |
| 1001 | 400 | 参数格式错误（类型 / 长度 / 范围） |
| 1002 | 400 | 缺失必填参数 |
| 2001 | 401 | 未登录 |
| 2002 | 401 | 凭证已过期（会话过期） |
| 2003 | 403 | 无权限（角色不满足，或资源级越权） |
| 2004 | 401 | 凭证无效（Token / 验证码错误） |
| 3001 | 404 | 资源不存在 |
| 3002 | 409 | 状态冲突 |
| 3003 | 409 | 资源重复（重复报名 / 重复申请 / 重复引用） |
| 4001 | 429 | 发送过频（验证码重发 / 提交冷却） |
| 4002 | 429 | 触发限流（登录超次 / 并发上限 / 冷却） |
| 5000 | 500 | 内部错误（不暴露详情） |
| 5001 | 502 | 上游服务失败（对象存储 / 沙箱链路） |

**模块专属码**：

| 码 | HTTP | 模块 | 说明 |
| --- | --- | --- | --- |
| 2005 `REGISTER_DISABLED` | 403 | users | 站点未开放注册（校验先于验证码消费） |
| 3004 `ORG_LAST_ADMIN` | 409 | orgs | 组织最后一名管理员不可撤销 / 移出 |
| 3005 `ORG_LAST_MEMBER` | 409 | orgs | 组织最后一名成员不可移出 |

新增模块专属码写在对应模块「错误码」节，`UPPER_SNAKE_CASE` 命名并标注 HTTP 与触发场景；代码中引用常量，不写死数字。

### 1.3 分页

- 列表统一 `?page=1&page_size=20`（`page ≥ 1`，`page_size ≤ 100`）
- 返回 `{ items, total, page, page_size }`
- 三张日志表深分页采用「延迟关联 + id 决胜列」（见 12.4）

---

## 2. 领域模型总览

```
users ─┬─< user_sessions
       ├─< user_roles >─ roles（scope='global' | 'org' → organizations | 'team' → teams）
       ├─< org_members >─ organizations
       ├─< team_members >─ teams（teams.org_id → organizations）
       ├─< problems（owner_id 署名；org_id → organizations / team_id → teams）
       │    · problem_sets（owner_id / team_id）· contests（owner_id / team_id）
       ├─< submissions
       └─< notifications · messages · posts · solutions · code_shares · comments · reports

problems ─┬─< problem_tag_relations >─ problem_tags
          ├─< test_cases
          ├─< problem_verifications
          ├─1 problem_counters
          ├─< problem_set_items >─ problem_sets
          ├─< contest_problems >─ contests
          ├─< solutions（评论经 comments.target_type='solution' 挂接）
          └─< submissions ─< submission_test_case_results

contests ─┬─< contest_problems · contest_registrations · contest_rankings
          └─< submissions
```

> `─<` 一对多，`>─` 多对一。Redis 只放短生命周期数据，Key 清单见 `operations.md`。

表清单：`users` `user_sessions` `roles` `user_roles` `organizations` `org_members` `teams` `team_members` `team_member_applications` `problems` `problem_counters` `problem_tags` `problem_tag_relations` `test_cases` `problem_verifications` `problem_sets` `problem_set_items` `contests` `contest_problems` `contest_registrations` `contest_rankings` `submissions` `submission_test_case_results` `sandbox_configs` `solutions` `code_shares` `comments` `reports` `notifications`* `messages`* `posts`* `system_configs` `request_logs` `login_logs` `exception_logs`

> `*` 规划中，仅建模型未实现端点。

---

## 3. 跨域规则

跨模块通用的三条规则只在此处定义，各模块章节不再重述。

### 3.1 所有权模型

权限按**资源归属**三分判定，与「谁创建」解耦：

| 资源 | 归属 | 管理权判定 |
| --- | --- | --- |
| 全站题目 / 题单 / 比赛 | `org_id` 与 `team_id` 均空 | `admin` 管全站；其余用户仅管**本人创建**（`owner_id`） |
| 组织题库题目 | `org_id` 非空 | 组织成员**全员读写**（含他人题与全组织草稿）；`owner_id` 仅为署名、无权限语义；组织名下团队的 team_creator / team_admin 有**只读**浏览权（供引用选题） |
| 团队资源 | `team_id` 非空 | 团队角色判定（team_creator ⊇ team_admin）；团队题目为快照题，裸路径拦截 |

- 全站内容创建入口仅 `admin`（`tutor` 已下线，公开内容收归 admin）
- 一个用户的**全局角色恰好一个**（`admin` / `user` 互斥）
- 组织 / 团队角色仅在对应上下文（`scope='org'/'team'` + `object_id`）叠加判定；一个用户可属多个组织 / 团队并持不同角色
- 越权一律 `2003`；资源不存在时同样按不可见处理，不泄漏存在性

### 3.2 可见性

**题目**按 `status + visibility` 双重控制，两者正交：

| 类型 | `org_id` / `team_id` | 可用 `visibility` | 题库中心可见 |
| --- | --- | --- | --- |
| 全站题 | 均空 | `private` / `public` | 仅 `public` |
| 组织题 | `org_id` 非空 | `org_visible` | 否（封闭上下文） |
| 团队题 | `team_id` 非空 | `admin_visible` / `team_visible` | 否（封闭上下文） |

- `status` 表达生命周期（`draft` / `published` / `archived`），`visibility` 表达开放范围；草稿仅管理者可见（组织题草稿对全组织可见可编辑，无个人私稿）
- 团队快照题（`source_problem_id` 非空）裸路径一律拦截，只能经团队上下文端点访问；**例外**：全局 admin 可经裸路径只读
- 跨可见性分支切换（public ↔ private、team_visible ↔ admin_visible）以外的改动返回 `1001`
- 题目被题单 / 比赛引用时不物理删除，下线走 `archived`

**题单 / 比赛**：全站 `public` / `private`；团队题单**恒** `team_visible`（无可见性入参）；团队比赛仅在团队空间展示。

### 3.3 编排候选（题单 / 比赛可选题目的唯一口径）

| 容器 | 候选集 |
| --- | --- |
| 全站题单 / 公开比赛 | 已发布 ∧ 全站公开；**一律排除**团队题与组织题（admin 亦然） |
| 团队题单 / 团队比赛 | 已发布 ∧（本团队题目 ∪ 全站公开）；组织题须先引用进团队 |
| 组织题库内 | 不设题单 / 比赛（组织不承载编排） |

- 编排保存与编排搜索端点按同一规则校验
- 私有题编入题单 / 比赛即视为经该上下文分发：**引用上下文内**（详情 / 交题）放行，**题库裸路径**仍按可见性门控

### 3.4 上下文隔离（限界上下文）

同一资源被多个上下文复用时（题库 / 题单 / 比赛 / 团队），每个上下文有独立路由与独立端点：

- 上下文内所有读写调用**本上下文模块的专属端点**，不跨模块直调（迪米特利斯法则）
- 端点在入口校验归属关系（资源属于该容器），装配与判题链路复用统一实现
- 前端路由与面包屑封闭在本上下文内，禁止把用户带离当前业务上下文

---

## 4. 用户与认证

### 4.1 `users`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| email | VARCHAR(255) | NOT NULL, UNIQUE | 登录邮箱（统一小写） |
| email_verified | BOOLEAN | NOT NULL DEFAULT false | 注册邮箱已验证 |
| password | VARCHAR(255) | NOT NULL | bcrypt/argon2 哈希，不存明文 |
| nickname | VARCHAR(64) | NOT NULL | |
| avatar_url | VARCHAR(512) | NULL | 站内完整文件 URL（`/api/v1/files/users/{uid}/avatar/{uuid}`）或可信外链 |
| signature | VARCHAR(255) | NULL | |
| theme | VARCHAR(32) | NOT NULL DEFAULT 'light' | 主题偏好 |
| editor_font_size | INT | NOT NULL DEFAULT 14 | 编辑器字号（11–24） |
| editor_font_family | VARCHAR(32) | NOT NULL DEFAULT 'jetbrains-mono' | 编辑器字体（白名单见前端 constants/editorFonts） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `frozen` / `banned` / `deleted` |
| frozen_until | TIMESTAMPTZ | NULL | 非空 = 短时冻结（到期自动恢复 active）；NULL = 人工冻结 |
| last_login_at | TIMESTAMPTZ | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`email`)、INDEX(`status`)

### 4.2 `user_sessions`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| token | VARCHAR(64) | NOT NULL, UNIQUE | 会话 Token（哈希存储） |
| device_info | VARCHAR(255) | NULL | 设备标识（`Chrome · Windows` 形式） |
| ip_address | INET | NULL | |
| user_agent | TEXT | NULL | |
| expires_at | TIMESTAMPTZ | NOT NULL | |
| revoked_at | TIMESTAMPTZ | NULL | 非空即已撤销 |
| last_active_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `expires_at`, `revoked_at`)

### 4.3 账号状态

| 状态 | 触发 | 恢复 | 登录 |
| --- | --- | --- | --- |
| `active` | 正常 | — | 允许 |
| `frozen` 冻结（短时封禁） | 登录失败超次（15 分钟窗口 5 次）；管理员限时冻结 | `frozen_until` 到期自动恢复；管理员可提前解冻 | 拦截 |
| `banned` 封禁 | 管理员主动封禁 | 仅人工解封 | 拦截 |
| `deleted` 注销 | 用户主动注销 | 不可恢复 | 拒绝 |

> 冻结是短时封禁（不涉及违规定性，到期自动恢复；`frozen_until` 为空的历史行仍需人工解冻）；封禁是管理员主动行为，仅人工解封。

### 4.4 邮箱规则与验证码

- **格式**（所有收邮箱入口统一校验，非法 `1001`）：总长 ≤254；local ≤64 且为点分 atom；domain ≥2 标签、每标签 1–63 位；TLD 2–63 位字母；拒绝 IP 字面量、引号地址、空白 / 控制字符 / 非 ASCII
- 大小写不敏感：去空白后统一小写（用于校验、查重、落库、Redis key、登录查询）
- **验证码存 Redis 不落库**：`email:code:<email>:<purpose>`（验证码 + 错误计数）、`email:resend:<email>:<purpose>`（重发间隔）；一次使用，校验通过即删；策略（有效期 / 重发间隔 / 最大尝试）见 `admin` 的 `auth_email` 配置域

### 4.5 数据所有权

- 只能读写本人资料与会话：SQL 必须带 `WHERE user_id = ?`
- 注销为软注销：`status='deleted'`，`email` 替换为脱敏值（`u<id>@invalid.local`）释放邮箱并保持唯一
- 会话撤销仅本人可执行；返回用户对象必须排除 `password`

### 4.6 端点

| 方法 | 路径 | 权限 | 说明 | 关键入参 |
| --- | --- | --- | --- | --- |
| POST | /auth/email-code | public | 发送验证码 | email, purpose |
| POST | /auth/register | public | 注册 | email, code, password, nickname |
| POST | /auth/login | public | 登录 | email, password |
| POST | /auth/logout | auth | 登出 | - |
| POST | /auth/reset-password | public | 重置密码 | email, code, new_password |
| POST | /auth/change-password | auth | 修改密码 | old_password, new_password |
| POST | /auth/change-email | auth | 换绑邮箱 | new_email, code |
| GET | /users/me | auth | 当前用户 | - |
| PUT | /users/me | auth | 更新资料（昵称 / 签名 / 主题 / 编辑器偏好 / `avatar_url` 完整 URL，不接受裸 oss_id） | 见 §4.1 |
| DELETE | /users/me | auth | 注销（软注销，需密码） | password |
| GET | /users/me/sessions | auth | 会话列表（带 `current` / `online`——5 分钟活跃窗口） | - |
| DELETE | /users/me/sessions/{sid} | owner | 注销指定会话 | - |
| DELETE | /users/me/sessions | auth | 下线其他设备（**物理删除**除当前外全部会话行 + 清缓存） | - |

### 4.7 关键行为

1. **注册**：`email-code`（purpose=register）→ `register` 通过后建用户（`email_verified=true`），验证码删除。`site.register_enabled=false` 返回 `2005` 且不消耗验证码；`email.verify_enabled=false` 时免验证码。
2. **登录**：校验密码 + 写 `user_sessions` + Redis 热点；失败超次触发短时冻结（同时清零失败计数）。
3. **同设备去重**：同 `user_id + device_info` 的旧有效会话在新登录时失效（revoked + 清缓存）。顺序为**先建新会话、后清理同设备旧会话（排除新 token）**——并发登录下收敛为一设备一会话；UA 无法识别的会话不参与去重。
4. **会话活跃回写**：Redis `session:active:<token_hash>`（TTL 5 分钟）做节流阀，窗口到期才回写 `last_active_at`；「在线中」= 最近 5 分钟有活动。

---

## 5. 组织

> 组织是多机构共用一个 OJ 的租户单元：admin 建组织并任命组织管理员；组织管理员拉人、建团队、维护组织题库。团队挂在组织下。

### 5.1 `organizations`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL, UNIQUE | 全站唯一 |
| description | TEXT | NULL | |
| avatar_url | VARCHAR(512) | NULL | 站内完整 URL 或可信外链 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` |
| created_by | UUID | NOT NULL, FK → users.id | 创建操作人（admin），仅审计署名 |
| disbanded_at | TIMESTAMPTZ | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`name`)、INDEX(`status`)

### 5.2 `org_members`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| org_id | UUID | NOT NULL, FK → organizations.id | |
| user_id | UUID | NOT NULL, FK → users.id | |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `removed` |
| added_by | UUID | NULL, FK → users.id | 拉人操作人 |
| joined_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| left_at | TIMESTAMPTZ | NULL | |
| note | VARCHAR(64) | NULL | 成员备注（本人可备注自己，org_admin 可备注任意成员），无权限语义 |

索引：PARTIAL UNIQUE(`org_id`, `user_id`) WHERE `status='active'`、INDEX(`user_id`)

### 5.3 组织角色（`user_roles`，`scope='org'`）

| code | 说明 |
| --- | --- |
| `org_admin` | 成员管理（拉人 / 移出 / 授予·撤销 org_admin）、组织信息、组织内建团队 |
| `org_member` | 组织题库全量读写（创建 / 编辑 / 验题 / 发布 / 归档 / 交题 / 自测） |

- `org_admin` ⊇ `org_member`；站点 admin 视同拥有全部组织管理权
- 被移出 / 组织解散时同步删除授权

### 5.4 组织题库

- **组织是内容所有者**：管理权按成员资格判定，`problems.owner_id` 仅署名
- 全员读写含草稿：无个人私稿，草稿箱视图即全组织草稿
- 封闭上下文：仅组织成员经组织端点访问；组织名下团队管理者额外获得只读浏览权
- 组织题不进题库中心、不得编入全站题单 / 公开比赛；跨组织不互通
- 管理动作（题面 / 测试点 / 验题 / 发布 / 归档）**复用 `/problems/{id}/...` 统一端点**，权限门按归属扩展（见 §3.1）；不为组织题库另建一套管理端点
- 解散为软解散：`status='disbanded'`，清理 org 授权与成员状态，题库题目归档，**名下团队级联软解散**

### 5.5 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | /orgs | admin | 创建组织（创建者不加入组织，仅记录 created_by；可任命初始 org_admin） |
| GET | /orgs/mine | auth | 我加入的组织（带 my_role / 成员数 / 团队数） |
| GET | /orgs/{id} | org 角色 | 组织详情（非成员 2003） |
| PUT | /orgs/{id} | org_admin | 编辑组织信息 |
| DELETE | /orgs/{id} | admin | 解散组织（软解散 + 级联） |
| GET | /orgs/{id}/members | org 角色 | 成员列表（昵称模糊） |
| GET | /orgs/{id}/member-candidates | org_admin / admin | 按邮箱**精确**查找可添加成员（带 `is_member`；不提供模糊搜索） |
| POST | /orgs/{id}/members | org_admin | 添加成员（可批量，已在册跳过） |
| DELETE | /orgs/{id}/members/{uid} | org_admin | 移出（最后一名 admin 3004 / 最后一名成员 3005） |
| PUT | /orgs/{id}/members/{uid}/admin | org_admin / admin | 授予 / 撤销组织管理员（不可撤销自己，2003） |
| PUT | /orgs/{id}/members/{uid}/note | 本人或 org_admin | 成员备注（≤64 字符，空串清除） |
| POST | /orgs/{id}/teams | org_admin | 创建团队（`org_id` 固定为本组织，创建者自动 team_creator） |
| GET | /orgs/{id}/teams | org 角色 | 组织名下团队列表 |
| GET | /orgs/{id}/problems | org 角色 | 组织题库列表（缺省 published；`status=draft` 为全组织草稿视图；归档不返回；带 `needs_reverification`） |
| POST | /orgs/{id}/problems | org_member | 组织题库建题（`visibility` 恒 `org_visible`，`referenced_at` 恒 NULL） |
| GET | /orgs/{id}/problems/{pid} | org 角色 | 组织题目详情（组织上下文统一入口） |

**管理端**：`GET /admin/orgs`（全量含已解散）、`GET /admin/orgs/{id}`、`GET /admin/orgs/{id}/members`、`PUT /admin/teams/{id}/org`（存量团队指派组织，迁移用）。

### 5.6 错误码

`3004` 最后一名管理员；`3005` 最后一名成员；`3001` 组织不存在；`3003` 组织名重复 / 重复添加成员；`2003` 非管理员执行管理操作 / 非成员访问 / 撤销自己；`1001` 参数错误。

---

## 6. 团队

> 团队挂在组织下（`teams.org_id`）。**创建入口为 `POST /orgs/{org_id}/teams`（org_admin 门）**，全局 `POST /teams` 已移除。

### 6.1 `teams`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(64) | NOT NULL | |
| description | TEXT | NULL | |
| avatar_url | VARCHAR(512) | NULL | 站内完整 URL 或可信外链 |
| creator_id | UUID | NOT NULL, FK → users.id | 自动成为 team_creator |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `disbanded` |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'private' | `public`（团队中心可见、可直接申请）/ `private`（仅凭邀请链接申请） |
| org_id | UUID | NULL, FK → organizations.id | 新建必填；存量可空，由 admin 指派后方可引用组织题库 |
| disbanded_at | TIMESTAMPTZ | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`creator_id`)、INDEX(`status`)、INDEX(`visibility`, `status`)

### 6.2 `team_members` / `team_member_applications`

`team_members`：`team_id` / `user_id` / `status`（`active` / `exited` / `kicked`）/ `joined_at` / `left_at` / `note`（≤64 字符，本人或团队管理者可写）。索引：PARTIAL UNIQUE(`team_id`,`user_id`) WHERE `status='active'`、INDEX(`user_id`)。

`team_member_applications`：`team_id` / `user_id` / `invite_token`（记录来源）/ `status`（`pending` / `approved` / `rejected`）/ `applied_at` / `reviewed_by` / `reviewed_at`。索引：PARTIAL UNIQUE(`team_id`,`user_id`) WHERE `status='pending'`、INDEX(`user_id`,`status`)。

> 成员表只记身份；团队角色在 `user_roles`（`scope='team'`、`object_id=team_id`）中查询。

### 6.3 团队角色

`team_creator`（创建时自动授权，⊇ team_admin，额外含「分配管理员」）/ `team_admin` / `team_member`（审批通过时授权）。退出 / 踢出 / 解散时同步删授权。

### 6.4 团队空间（题目 / 题单 / 比赛）

团队空间用**独立端点**（`/teams/{team_id}/...`），与公开上下文互相隔离。

- **团队题目 = 引用制（快照复制）**：`POST /teams/{team_id}/problems/references` 复制新题，继承题面 / 样例 / 生效测试点（MinIO 对象复制）/ 标签 / 验题发布状态；`source_problem_id` 指向源题（同团队同源唯一，重复 3003）；`referenced_at` = 引用时间。**统计从零累计**（纯团队口径），快照后两题独立演进。来源池 = 本组织组织题库 ∪ 全站公开已发布；团队上下文**直建已移除**
- **团队题单**：团队管理者直接创建，恒 `team_visible`（无可见性入参）；编排候选见 §3.3
- **团队比赛**：`contest_type='team'`，创建 / 编排走团队端点；报名叠加团队成员校验
- **隔离**：团队题不得编入全站题单 / 公开比赛；团队题单 / 比赛不出现在公开中心

### 6.5 端点

**团队与成员**：

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /teams | public / auth | 团队中心：仅 public + active；`mine=true`（须登录）改为本人在册团队。**成员判定以 `team_members.active` 为唯一口径**（角色残留不得令非成员带 my_role） |
| GET | /teams/mine | auth | 我的团队列表 |
| GET | /teams/{id} | auth（成员） | 团队详情（非成员 2003，前端提供申请出口） |
| PUT | /teams/{id} | team_creator / team_admin | 编辑信息（名称 / 简介 / 头像 / 可见性，切换即时生效） |
| GET | /teams/{id}/members | team 角色 | 成员列表 |
| POST | /teams/{id}/invites | team_creator / team_admin | 生成邀请链接（Redis） |
| GET | /teams/invites/{token} | public | 解析邀请链接 |
| POST | /teams/{id}/applications | auth | 提交申请（private 团队无 token 返回 2003） |
| GET | /teams/{id}/applications | team_creator / team_admin | 申请列表 |
| POST | /teams/{id}/applications/{aid}/review | team_creator / team_admin | 审批（通过写 team_member 授权） |
| PUT | /teams/{id}/members/{uid}/admin | 仅创建者或 admin | 分配 / 取消团队管理员 |
| PUT | /teams/{id}/members/{uid}/note | 本人或团队管理者 | 成员备注 |
| DELETE | /teams/{id}/members/{uid} | team_creator / team_admin | 踢出（不可移除创建者，不可移除自己——自退走 exit） |
| POST | /teams/{id}/exit | auth（成员） | 主动退出 |
| DELETE | /teams/{id} | 仅创建者或 admin | 解散（admin 兜底代解散） |

**团队空间**：

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /teams/{tid}/problems | team 角色 | 团队题库（成员见 published+team_visible；管理者仅见已发布；带 `referenced_at` / `needs_reverification` / 计数） |
| POST | /teams/{tid}/problems/references | 管理者 | 引用题进团队（来源池外 2003、二次引用 3003） |
| GET | /teams/{tid}/problems/referenceable | 管理者 | 引用候选搜索（已发布 + 非团队题 +（本组织组织题 ∪ 全站公开）+ 未被本团队引用） |
| GET | /teams/{tid}/problems/arrangeable | 管理者 | 编排候选（见 §3.3） |
| GET | /teams/{tid}/problems/{pid} | team 角色 | 团队题目详情（归属 + 可见性门） |
| PUT | /teams/{tid}/problems/{pid}/statement | 题目管理者 | 团队上下文编辑题面 |
| POST | /teams/{tid}/problems/{pid}/submissions | team 角色 | 团队内交题（`practice`） |
| POST | /teams/{tid}/problems/{pid}/run-code | team 角色 | 团队内自测 |
| GET/POST/PUT | /teams/{tid}/problem-sets* | team 角色 / 管理者 | 题单列表 / 详情 / 创建 / 编排 / 下线 / 题单内题目 / 交题 / 自测 |
| GET/POST/PUT | /teams/{tid}/contests* | team 角色 / 管理者 | 比赛列表 / 详情 / 创建 / 编辑 / 报名 / 题目 / 交题 / 榜单 / 提交记录 / 解冻 / 公告 / 延时 / 封榜时间 / 滚榜 |

> 团队题目与团队题单 / 比赛的详情、交题、自测**必须**走团队端点；团队比赛以 `/teams/:teamId/contests/:cid` 系列前端路由呈现，内部导航不跳出团队前缀。全站 `GET /contests/{id}` 对团队成员放行（供 admin 只读浏览）。

**管理端（只读 + 代解散）**：`GET /admin/teams`（全量含已解散）、`GET /admin/teams/{id}`、`/members`、`/problems`、`/problem-sets`、`/contests`（只读浏览）、`POST /admin/teams/{id}/disband`（治理逃生门）。

### 6.6 错误码

`3001` 团队 / 邀请链接 / 题目不存在；`2003` 越权管理 / 非成员访问 / 私有团队无 token 申请；`3003` 重复申请 / 二次引用 / 编排重复；`3002` 邀请过期 / 团队已解散；`1001` 编排含不可见题目 / 可见性非法。

---

## 7. 题库

### 7.1 `problems`

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(255) | NOT NULL | |
| background | TEXT | NOT NULL DEFAULT '无' | 题目背景（Markdown，**必填**，渲染于题面之前） |
| description | TEXT | NOT NULL | 题面（Markdown） |
| input_description | TEXT | NULL | 输入说明（Markdown，**必填**；列可空以兼容存量） |
| output_description | TEXT | NULL | 输出说明（同上） |
| note | TEXT | NULL | 题面说明（可选，渲染于题面最后；PUT 空串 = 清空） |
| solution | TEXT | NULL | 官方题解（Markdown，仅管理者可读写） |
| samples | JSONB | NOT NULL DEFAULT '[]' | 展示样例 `[{input, output, explanation?}]`，≤10 组、各 ≤64KB；**不参与判题** |
| samples_updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 重验判定依据 |
| active_case_ids | JSONB | NOT NULL DEFAULT '[]' | 生效测试点 id（判题唯一数据来源） |
| pending_case_ids | JSONB | NULL | 暂存测试点 id；**NULL = 无暂存改动**，数组（含 `'[]'`）= 有改动 |
| spj_oss_id | VARCHAR(512) | NULL | 生效特判程序源码 key（NULL = 非 SPJ 题） |
| pending_spj_oss_id | VARCHAR(512) | NULL | 暂存特判；NULL = 无改动，key = 覆盖，`''` = 暂存移除 |
| case_status | VARCHAR(16) | NOT NULL | `empty` / `to_verify` / `to_reverify` / `verified` / `ok` |
| cases_revision | INT | NOT NULL DEFAULT 0 | 集合写操作自增（预留 CAS） |
| pending_verified | BOOLEAN | NOT NULL DEFAULT false | 暂存集已验待生效（任何新暂存写入即清除） |
| time_limit_ms | INT | NOT NULL DEFAULT 1000 | **C++ 基准**，按语言比例换算 |
| memory_limit_mb | INT | NOT NULL DEFAULT 256 | **C++ 基准**，按语言比例换算 |
| difficulty | INT | NULL, CHECK (NULL OR >= 0) | 难度分（手动填写，NULL=未评分） |
| team_id | UUID | NULL, FK → teams.id | 与 `org_id` 互斥 |
| org_id | UUID | NULL, FK → organizations.id | 与 `team_id` 互斥 |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者（组织题仅署名） |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | 见 §3.2 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'draft' | `draft` / `published` / `archived` |
| verified_at | TIMESTAMPTZ | NULL | 「已验题」≡ 本字段非空（API 字段派生输出） |
| verified_by | UUID | NULL, FK → users.id | |
| published_at | TIMESTAMPTZ | NULL | |
| referenced_at | TIMESTAMPTZ | NULL | 非空 = 团队引用快照题 |
| source_problem_id | UUID | NULL, FK → problems.id ON DELETE SET NULL | 快照源题（`uq_problems_team_source` 防重） |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK（归属与可见性匹配）：

```sql
CHECK (
  (team_id IS NULL AND org_id IS NULL AND visibility IN ('private','public')) OR
  (org_id IS NOT NULL AND team_id IS NULL AND visibility = 'org_visible') OR
  (team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible'))
)
CHECK (status <> 'published' OR verified_at IS NOT NULL)
```

索引：INDEX(`owner_id`)、INDEX(`team_id`,`visibility`,`status`)、INDEX(`org_id`,`status`)、INDEX(`visibility`,`status`)、GIN(`title` gin_trgm_ops)

### 7.2 `problem_counters`

1:1 于 `problems`（PK 即 FK，CASCADE），判题终态 upsert 原子累加，避免高频写打热行。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| problem_id | UUID | PK, FK → problems.id (CASCADE) |
| submission_count | INT | 终态提交数（排除 verify 与 system_error） |
| accepted_count | INT | AC 提交数（同口径） |
| updated_at | TIMESTAMPTZ | |

- 写：`INSERT ... ON CONFLICT (problem_id) DO UPDATE ... + 1`（并发安全）
- 读：返回原始计数，通过率由前端现算（无提交显示 `--`）；漂移可用 `submissions` GROUP BY 重算对账

### 7.3 标签

`problem_tags`：`name` UNIQUE、`color`、`status`（`active` / `archived`）。
`problem_tag_relations`：`problem_id` / `tag_id`，UNIQUE(`problem_id`,`tag_id`)。

- 仅 admin 维护；**归档不删除**：既有关联保留并继续展示，但不再可选、不出现在激活列表
- 打标：请求体 `tags: string[]`（≤8、去重），值为激活标签名；未知 / 已归档返回 `1001`

### 7.4 `test_cases`

测试点行**不可变版本化**，集合成员资格由 `active_case_ids` / `pending_case_ids` 定义。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | PK，行身份永不变更、永不删除（历史结果外键恒有效） |
| problem_id | UUID | NOT NULL, FK |
| name | VARCHAR(64) | NULL |
| input_oss_id | VARCHAR(512) | 对象 key `problems/{pid}/cases/{cid}/input` |
| expected_output_oss_id | VARCHAR(512) | 对象 key `.../output` |
| origin_id | UUID | NULL, FK → test_cases.id（改版时指向被取代原行） |
| sort_order | INT | NOT NULL DEFAULT 0 |
| created_at / updated_at | TIMESTAMPTZ | |

- 行一经被任一列表引用即**不可变**：改名 / 换内容一律新增行
- 保存 = 写 pending：未改动点沿用原 id（零拷贝），改动点为新行 id，删除点不出现
- 验题通过 + 显式 apply 才 `active := pending`；被取代旧行退役留档，不清理
- **展示样例不落本表**（存 `problems.samples`），正式判题只用 active 集

### 7.5 SPJ 特判程序

C++17 单文件 checker，存 MinIO，`problems` 只存 key，与测试点共用「暂存 → 验题 → 晋升」语义：

- 生效 `spj_oss_id`；暂存 `pending_spj_oss_id`（NULL / key / `''`）
- `PUT /problems/{id}/spj`（≤256KB UTF-8）、`DELETE`（写暂存移除）、`GET`（回读目标状态，暂存优先）
- **判定集**：验题用暂存 SPJ（NULL 退化生效集）；练习 / 比赛恒用生效 SPJ
- 晋升随 `POST /problems/{id}/test-cases/apply` 单事务一并完成
- `data_version` 指纹包含 SPJ 对象 key
- 判题节点按 `problem_id + data_version` 缓存编译产物 `spj.bin`，同版本只编译一次；`spj.cpp` mtime 更新则失效重编

### 7.6 `problem_verifications`

`problem_id` / `verifier_id`（通过时的实际提交人）/ `status`（`pending` / `passed` / `failed`）/ `language` / `code` / `comment` / 时间戳。索引 INDEX(`problem_id`,`status`)。

**验题邀请链接**存 Redis（`verify_invite:{token}` → `{"problem_id": "..."}`，TTL = 有效期小时数），吊销即删 key，不建表。提交验题代码身份不限（存在 pending 记录时任何登录用户均可提交）。

### 7.7 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /problems | public / auth | 题库列表。默认仅 published+public；`scope=mine` 管理视图（admin 全量 / 其余见所在组织题聚合 ∪ 本人创建）；`mine=true` 仅本人已发布全站题；可叠加 `status` / `ownership`（`solo`/`org`/`team`）/ 难度闭区间；列表项带 `needs_reverification`、`difficulty`、计数；登录带 `solved`（true/false/null） |
| GET | /problems/tags | public | 激活标签列表 |
| GET | /admin/tags | admin | 全量标签（含归档） |
| POST/PUT | /admin/tags、/admin/tags/{id} | admin | 新增 / 改名改色 |
| POST | /admin/tags/{id}/archive | admin | 归档 |
| GET | /problems/{id} | public / owner | 题目详情（按可见性；**不含测试点**） |
| GET | /problems/{id}/editorial | 题目可见者 | 官方题解（community 模块注册） |
| GET | /problems/{id}/test-cases | 题目管理者 | 测试点列表（目标状态合并视图 + `updated_at`） |
| POST | /problems | admin | 创建全站题（组织题走 `/orgs/{id}/problems`；团队题只来自引用） |
| PUT | /problems/{id} | 题目管理者 | 编辑题目（`tags` 全量替换；`difficulty` 非负整数） |
| PUT | /problems/{id}/test-cases | 题目管理者 | 全量替换**暂存集**（旧对象异步清理；生效集不动） |
| PATCH | /problems/{id}/test-cases | 题目管理者 | 增量改暂存集（upserts / delete_ids；同 id 不得两处出现 1001；未知 id 3001） |
| POST | /problems/{id}/test-cases/apply | 题目管理者 | 显式生效（测试点 + SPJ 一并晋升；无暂存 3002、未验 3002） |
| PUT/DELETE/GET | /problems/{id}/spj | 题目管理者 | 设 / 移除 / 回读暂存 SPJ |
| PUT | /problems/{id}/samples | 题目管理者 | 全量替换展示样例（同时更新 `samples_updated_at`） |
| POST | /problems/{id}/verify | 题目管理者（发起）/ auth（提交） | 双模式：`code+language` 为提交，否则为发起 |
| GET | /verify-invites/{token} | public | 解析验题邀请（返回题面与样例，不含测试点与题解） |
| POST | /problems/{id}/publish | 题目管理者 | 发布（须已验 + active 非空 + 无暂存改动 + 样例未晚于 verified_at） |
| POST | /problems/{id}/archive | 题目管理者 | 归档 |
| POST | /admin/problems/import | admin | FPS 题库导入（ZIP / XML） |
| GET | /admin/problems/{id}/export | admin | 单题导出 fps.xml |
| GET | /admin/problems/export | admin | 批量导出 ZIP（`ids` ≤20） |

> 测试点 / 样例不走独立上传：`input` / `expected_output` 内容（各 ≤8MB）由后端生成 key 并上传 MinIO；样例直接存库（≤64KB）。不生成测试点归档 ZIP，前端 ZIP 只在浏览器内解压。

### 7.8 FPS 导入 / 导出

导入（`POST /admin/problems/import` 与 CLI `python -m scripts.import_fps_problems` 共用核心），逐题建库：

- 有测试点且无特判 → `published`（回填 verified_at / published_at）
- 无测试点 → `draft`
- `<sample_input>` / `<sample_output>` → 写 `problems.samples`
- `<spj>` 带源码 → **恒 `draft`** 且写入暂存（走验题 → apply）
- `<spj>` 仅标记无源码 → 跳过（无法重建 checker）
- `<difficulty>` → 写 `difficulty`；同标题 → 跳过；单题失败不阻断
- 导入人即 owner，可见性 public；单次最多 20 题（超出 `truncated=true`）；导入压缩包 ≤64MB、单 XML ≤64MB、累计解压 ≤256MB

导出**只导出生效集**（active 测试点、生效 SPJ、samples）；字段反向映射（`note`→`hint`、`background`→`source`、`difficulty`→`<difficulty>`）；单次 ≤20 题、总量 ≤256MB；附件下载为原始响应不经信封。

**题面图片双向转换**（只认 Markdown `![](url)`）：导入时 base64 落 MinIO 换站内 URL（单张 ≤5MB、单题 ≤20MB）；导出时站内插图转回 base64（自包含、可跨站迁移）。

### 7.9 错误码

`3001` 题目不存在；`2003` 不可见 / 越权；`3002` 发布未验 / 归档后编辑；`1001` 测试点类型或大小不符；`3003` 重复发起验题。

---

## 8. 题单

### 8.1 `problem_sets` / `problem_set_items`

`problem_sets`：`title` / `description` / `team_id`（NULL=全站）/ `owner_id` / `visibility`（`public` / `private` / `team_visible`）/ `status`（`active` / `archived`）。

```sql
CHECK (
  (team_id IS NULL     AND visibility IN ('public','private')) OR
  (team_id IS NOT NULL AND visibility IN ('team_visible'))
)
```

索引：INDEX(`owner_id`,`status`)、INDEX(`team_id`,`visibility`)。

`problem_set_items`：`problem_set_id` / `problem_id` / `sort_order` / `added_by` / `created_at`。索引 UNIQUE(`problem_set_id`,`problem_id`)、INDEX(`problem_id`)。

### 8.2 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /problem-sets | public / auth | 题单中心：仅公开且未下线的全站题单；`mine=true` 为本人题单 |
| POST | /problem-sets | admin | 创建全站题单（`team_id` 为空） |
| GET | /problem-sets/{id} | public / owner | 题单详情（条目按 sort_order，带题目元信息与 `solved`；`can_manage` 标记） |
| GET | /admin/problem-sets | admin | 管理视图（全量；`ownership` 过滤 solo/team） |
| GET | /problem-sets/{id}/problems/{pid} | public / owner | 题单内题目详情（**统一入口**，题单可见 + 归属校验） |
| POST | /problem-sets/{id}/problems/{pid}/submissions | auth | 题单内交题（`practice`） |
| PUT | /problem-sets/{id} | admin | 编辑元信息 |
| PUT | /problem-sets/{id}/items | admin | 编排（全量替换；候选见 §3.3；重复 3003） |
| POST | /problem-sets/{id}/archive | admin | 下线 |

> 团队题单的创建 / 编排 / 下线 / 列表 / 详情走 `/teams/{tid}/problem-sets*`（§6.5），不走本模块统一入口。

### 8.3 错误码

`3001` 题单不存在；`2003` 越权 / 不可见；`3003` 题目重复；`1001` 编排含未发布或不可见题目 / 可见性非法。

---

## 9. 比赛

### 9.1 `contests`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | PK |
| title | VARCHAR(128) | NOT NULL |
| description | TEXT | Markdown |
| announcement | TEXT | 公告（赛时可改，空 = 未发布） |
| announcement_updated_at | TIMESTAMPTZ | NULL |
| logo | VARCHAR(512) | 经 `/files/upload/image` 上传的 URL |
| contest_type | VARCHAR(16) | `public` / `team` |
| team_id | UUID | NULL, FK → teams.id |
| owner_id | UUID | NOT NULL, FK → users.id |
| rule_type | VARCHAR(8) | `ACM` / `IOI` |
| start_time / end_time | TIMESTAMPTZ | NOT NULL |
| register_start_time / register_end_time | TIMESTAMPTZ | NOT NULL |
| freeze_offset_seconds | INT | NOT NULL DEFAULT 0 | 封榜 = 结束前 N 秒 |
| board_frozen | BOOLEAN | NOT NULL DEFAULT false |
| frozen_at | TIMESTAMPTZ | NULL | 进入封榜时刻（滚榜揭晓边界） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'scheduled' | `scheduled` / `running` / `finished` |
| created_at / updated_at | TIMESTAMPTZ | |

```sql
CHECK (register_end_time <= end_time)
```

索引：INDEX(`status`,`start_time`)、INDEX(`team_id`,`contest_type`)。

### 9.2 关联表

`contest_problems`：`contest_id` / `problem_id` / `letter` / `sort_order` / `score`（IOI 单题分值，默认 100；ACM 恒 0）。UNIQUE(`contest_id`,`problem_id`)。

`contest_registrations`：`contest_id` / `user_id` / `status`（`registered` / `cancelled`）。UNIQUE(`contest_id`,`user_id`)。

`contest_rankings`：`contest_id` / `user_id` / `problem_id` / `accepted` / `accepted_at` / `attempts` / `penalty` / `score` / `is_frozen`（历史兼容标记）。UNIQUE(`contest_id`,`user_id`,`problem_id`)。

### 9.3 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | /contests | public | 比赛中心（公开赛） |
| GET | /admin/contests | admin | 管理视图（公开 + 团队，全部状态） |
| GET | /contests/{id} | public / owner | 比赛详情（题目带本场 `solved`） |
| GET | /contests/{id}/problems | auth（见窗口规则） | 比赛题目列表 |
| GET | /contests/{id}/problems/search | 管理角色 | 编排候选搜索（§3.3） |
| POST | /contests | admin（公开）/ 团队管理者（团队） | 创建 |
| PUT | /contests/{id} | 同上 | 编辑（`status != scheduled` 时拒绝全部字段改动，3002） |
| POST | /contests/{id}/register | auth | 报名 |
| PUT | /contests/{id}/announcement | 管理角色 | 更新公告（赛时可改） |
| POST | /contests/{id}/extend | 管理角色 | 赛时延时（新 end_time 必须更晚） |
| PUT | /contests/{id}/freeze-time | 管理角色 | 调整 / 取消封榜（已封榜或已结束 3002） |
| GET | /contests/{id}/scoreboard-show | 管理角色 | 滚榜数据包（只读不解冻） |
| GET | /contests/{id}/board | auth | 榜单（封榜时按快照展示） |
| GET | /contests/{id}/board/{uid}/{pid}/accepted | auth（管理随时 / 赛后） | 单格 AC 提交 |
| POST | /contests/{id}/unfreeze | 管理角色 | **仅赛后**手动解冻（running 时 3002） |
| GET | /contests/{id}/problems/{pid} | auth（见窗口规则） | 比赛内题目详情（统一入口） |
| POST | /contests/{id}/problems/{pid}/submissions | auth | 比赛交题（赛后自动标记补题） |
| GET | /contests/{id}/submissions | 管理随时 / 赛后所有登录用户 | 提交记录列表 |
| GET | /contests/{id}/submissions/{sid} | 同上 | 提交详情（统一入口） |
| GET | /users/me/contests | auth | 我的比赛 / 报名 |

**窗口规则**：赛前（`now < start_time`）题目仅管理角色可见；赛中须**已报名**；赛后向所有登录用户开放（补题不计榜单）。未报名者赛后只能看公开题，私有题按 `3001` 处理（不泄漏存在性）。`contest_id` 由服务端从请求上下文推导，不信任客户端。

**详情页 tab**：赛前对非管理角色隐藏，赛中仅已报名可见，管理角色随时可见，赛后全员恢复。

### 9.4 计分

- **ACM**：全测试点通过才有分（AC = 单题满分，否则 0）；罚时 = 首次通过时间 + 首次通过前错误提交数 × 罚时系数（默认 20 分钟）；派题携带 `stop_on_failure` 短路
- **IOI**：每题取历史最高分，总分 = 各题最高分之和；单点分值 = 单题满分 ÷ 测试点数
- 榜单条件更新（避免并发覆盖）：错误提交 `attempts+1 WHERE accepted=false`；首次通过 `accepted=true, accepted_at=… WHERE accepted=false`（幂等）；IOI `score = GREATEST(score, :new)`

### 9.5 封榜与解冻

- 封榜由 `contest_transition` 周期任务按 `freeze_offset_seconds` 自动触发：置 `board_frozen=true` + 记 `frozen_at`，同时**按 submissions 重算截至 `frozen_at` 的榜单快照**——封榜是「只统计封榜时刻前」，不是隐藏整张榜
- 封榜期提交以 `Submission.created_at` 为界；封榜后新提交只落 `submissions`，不更新榜单行
- **解冻只能由管理角色手动触发且仅赛后可用**；比赛结束**不自动解冻**

### 9.6 错误码

`3001` 比赛不存在；`2003` 未报名 / 非团队成员 / 赛前题目不可见；`3003` 重复报名；`3002` 报名截止 / 已开始或已结束 / 解冻时机错误；`1001` 编排含未发布或不可见题目；`4002` 全局并发上限。

---

## 10. 判题与沙箱

### 10.1 `submissions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | PK |
| user_id | UUID | NOT NULL, FK |
| problem_id | UUID | NOT NULL, FK |
| contest_id | UUID | NULL, FK（`submit_type='contest'`） |
| verification_id | UUID | NULL, FK（`submit_type='verify'`） |
| submit_type | VARCHAR(16) | `practice` / `contest` / `verify` |
| rule_type | VARCHAR(8) | `ACM` / `IOI` 赛制快照（练习 / 验题为 NULL） |
| language | VARCHAR(32) | `python3.12` / `cpp17` / `java21` |
| code | TEXT | 应用层按 UTF-8 字节校验 ≤64KB |
| status | VARCHAR(24) | `pending` / `judging` / `accepted` / `wrong_answer` / `time_limit_exceeded` / `memory_limit_exceeded` / `output_limit_exceeded` / `runtime_error` / `compile_error` / `system_error` |
| score | INT | 服务端按赛制派生 |
| time_used_ms / memory_used_kb | INT | 峰值 |
| error_message | TEXT | 编译错误 / 运行错误 |
| is_after_contest | BOOLEAN | 赛后补题标记 |
| created_at / updated_at | TIMESTAMPTZ | |

索引：INDEX(`user_id`,`problem_id`,`created_at DESC`)、INDEX(`contest_id`,`created_at`)、INDEX(`verification_id`)、INDEX(`status`)。

```sql
CHECK (
  (submit_type='practice' AND contest_id IS NULL     AND verification_id IS NULL) OR
  (submit_type='contest'  AND contest_id IS NOT NULL AND verification_id IS NULL) OR
  (submit_type='verify'   AND verification_id IS NOT NULL AND contest_id IS NULL)
)
```

### 10.2 `submission_test_case_results`

`submission_id` / `test_case_id`（ON DELETE SET NULL，历史结果保留）/ `status` / `time_used_ms` / `memory_used_kb` / `score` / `output`（兼容列，新结果写空串；历史数据为 MinIO key，不再读取）/ `message`（SPJ stdout ≤2KB，非 SPJ 为 NULL）/ `created_at`。

UNIQUE(`submission_id`,`test_case_id`) WHERE `test_case_id IS NOT NULL`、INDEX(`test_case_id`)。

> **运行输出不保存、不在提交详情回传**（生产单点上限 5MB×20 点会形成 100MB 级 JSON，详见 §10.10）；**期望输出不记录 / 不返回**（防反推答案）。用户自测 stdout 仍按 §10.8 即时回传，不落库。

### 10.3 `sandbox_configs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| language | VARCHAR(32) | UNIQUE |
| cpu_limit | INT | CPU 时间上限（ms） |
| time_ratio / memory_ratio | REAL | 有效限制 = 题目限制 × 比例（cpp17 = 1.0 基准） |
| memory_min_mb | INT | 有效内存下限 |
| process_limit | INT | 进程数 |
| filesystem_readonly | BOOLEAN | 默认 true |
| output_limit_kb | INT | 输出上限（默认 5120） |
| disk_quota_mb | INT | 沙箱可写区配额 |
| cpu_cores | INT | 核数上限 |
| network_enabled | BOOLEAN | 默认 false |
| is_enabled | BOOLEAN | 默认 true |

> 节点运行时状态（在线 / 负载 / CPU / 内存）为热数据存 Redis `sandbox:node:<id>`，不落库。

### 10.4 语言限制换算

- 有效时间 = `problems.time_limit_ms × time_ratio`（向下取整）
- 有效内存 = `max(memory_limit_mb × memory_ratio, memory_min_mb)`
- `cpp17` 固定 1.0；`java21` / `python3.12` 用平台默认比例，可在 `sandbox_configs` 调整
- 全局语言级配置，**不做 per-problem 覆盖**

### 10.5 赛制计分

提交行原生携带 `rule_type`，派题与计分按快照执行，不依赖比赛上下文：

- **ACM**：全通过 = 单题满分（`contest_problems.score`，未配置 100）否则 0；派题带 `stop_on_failure=true`——节点在首个非 accepted 点后停止，仅回传已执行点
- **IOI / 练习 / 验题**：单点分值 = 满分 ÷ 点数，仅通过计分；练习 / 验题满分 100

### 10.6 SPJ 判定协议

```
<workdir>/spj <input> <user_out> <answer>
```

- 退出码：`0` = accepted；`3` / `4`（testlib `_died` / `_fail`）= 整个提交 `system_error`；其余 = wrong_answer（含 `_wa`=1、`_pe`=2；`16+分值` 部分分不支持）
- stdout（UTF-8 ≤2KB）作为该测试点 `message` 落库
- 限制：编译预算与提交代码一致、每作业编译一次（不跨作业缓存）；运行时间 `max(2×单点时限, 5000ms)`、输出上限 16KB
- 特判程序自身 TLE / MLE / RE / 超限 → 整个提交 `system_error`，`error_message` 固定 `special judge program failed`，**不回传编译器输出或 stderr**（防泄露源码）

### 10.7 端点

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | /submissions | auth | 提交判题 |
| GET | /submissions/{id} | owner | 提交详情（逐测试点状态 / 用量 / SPJ 信息；不含运行输出与期望输出） |
| GET | /submissions | auth | 本人提交历史 |
| GET | /problems/{id}/submissions | 题目管理者 | 题目全员提交列表 |
| GET | /problems/{id}/submissions/{sid} | 题目管理者 | 题目视角提交详情 |
| POST | /problems/{id}/run-code | auth | 用户自测（不落库不计分） |
| GET | /sandbox/health | admin | 沙箱节点健康 |
| GET | /admin/submissions | admin | 全站提交面板 |

**提交校验**：语言须在 `sandbox_configs` 白名单且启用；代码 ≤64KB；user+problem 冷却（4001）+ 全局并发上限（4002）。
**越权**：`submit_type=contest` 的 `contest_id` 由服务端推导；`submit_type=verify` 校验 `verification.verifier_id` 与当前用户一致。

### 10.8 用户自测

- 输入：代码 + 语言 + 可选 stdin（各 ≤64KB）；输出：仅 stdout 与运行元信息（状态 / 耗时 / 内存 / 错误摘要）
- 每次独立，无比对、无期望输出；不落库、不写对象存储
- 限制以该题限制为基准按语言比例换算；语言白名单取 `sandbox_configs`
- 频控：`judge:selftest:` 冷却 + 全局并发上限；作业仅存在于网关内存，节点断线即置错，整链路 120s 兜底

### 10.9 判题流程（gRPC 网关）

```
提交 → 建 submissions(pending)（语言白名单 / 冷却 4001 / 并发 4002）
     → dispatch：只选 task_count < capacity 的活节点，任务数最少优先
       build_job_bundle 原子认领（UPDATE ... WHERE status='pending'）后沿双向流推 SubmitJob
     → 满载 / 无在线节点：保持 pending；节点腾容量或注册 / 重连即踢醒巡检
节点 → FetchProblemData 按 1MB 分块拉测试点到 /cache（未命中时，同题并发合并，网关全局 ≤4 路）；按比例换算有效限制
     → isolate 编译一次 + 逐点运行（ACM 串行短路；IOI/练习/验题默认 4 点并发）
     → 回传 JudgeResult（不含逐点 stdout，仅状态 / 用量 / SPJ message）；服务端写 submission_test_case_results + submissions
       + problem_counters（练习/比赛终态）或 verification 回写（验题）
```

**维护循环**（进程内 asyncio，与网关同生命周期，无 Celery）：

- 30s 周期兜底；pending 不设滞留门槛（有空位即派），巡检只取提交 id 并按在线节点空闲容量限制单轮派发，无容量时空转不抢 Redis 锁
- `judging > 5min` 复位重派（先下发 CancelJob）
- Redis SETNX 防重复投递：失败 5s 冷却、成功 300s 在途保护
- 断线 / 超时回收计入 `judge:attempts:<sid>`，满 3 次转 `system_error`

### 10.10 节点网关协议

`.proto` 见 `protos/pigeonoj/judge/v1/judge.proto`（stub 生成于 `app/rpc/gen` 与 `src/judge/node/gen`，勿手改）。

- `Connect(stream NodeMessage) returns (stream ServerMessage)`：首条 Register 带令牌（`JUDGE_GATEWAY_TOKENS` 其一），不符 UNAUTHENTICATED。上行 Heartbeat / JudgeResult / RunCodeResult；下行 SubmitJob / RunCodeJob / CancelJob
- Heartbeat 带 `running_tasks` 与宿主 `cpu_usage` / `memory_usage`（0-100）；`load` 由服务端按 capacity 计算
- Register 带能力位 `supports_spj`：网关派发 SPJ 题只选支持节点（无支持节点 → `system_error`），旧节点默认 false（防止退化为默认比对静默误判）
- `FetchProblemData(ProblemDataRequest) returns (stream FileChunk)`：按 `data_version` 流式传 manifest / cases / spj.cpp，单文件按 1MB 拆片（同 path 连续追加），令牌经 metadata `x-node-token`；服务端逐文件有界预取、同时最多 4 路，峰值内存约 16MB，不整包加载
- **数据指纹** = `sha256(测试点数量 | 最大 updated_at | 特判程序对象 key)`，**按判定集统计**（练习 / 比赛用生效集，验题用暂存集）；节点按 `<problem_id>-<data_version>` 缓存，跨提交复用；同题同版本并发拉取合并为一次，缓存目录写入在线程中按序完成
- **断线语义**：连接断开即离线，其名下 in-flight 重置 pending 重派；在途自测即时置错；判题写入幂等
- **同 ID 重连竞态**：重连时 in-flight 移交新连接并清空旧副本；旧（僵尸）连接的迟到清理视为空回收
- **僵尸连接防护**：单条消息处理失败只记日志不终止流；派发与并发统计跳过超过 `max(2×心跳间隔, 心跳 TTL)` 无上行消息的节点

### 10.11 执行规范

| 项 | 规范 |
| --- | --- |
| 时间测量 | wall-clock 与 CPU 双限：`--cg --time=<秒.毫秒>` + `--wall-time=<有效时间+500ms>`；执行器另设 `有效时间+15s` 强杀。`status=TO` / CPU 超限 / wall 超 `有效时间+500ms` → TLE。展示取 meta `time`（CPU），wall 超限时取 `time-wall`（避免 sleep 类显示 0ms） |
| 内存测量 | 峰值 RSS（含子进程）为口径。`--cg-mem=<有效内存 KB>` 限制整组 RSS；`cg-oom-killed` 或峰值超限 → MLE；C++ / Python 另以 `--mem` 封顶地址空间（Java 不加，JVM 虚拟预留大）。展示取 `max-rss`（缺失取 `cg-mem`） |
| 入口约定 | C++ `Main.cpp`、Java 主类固定 `Main`、Python `Main.py` |
| 编译命令 | cpp17 `g++ -std=c++17 -O2 -o /box/out/Main`；java21 `javac -d /box/out`；python 免编译。编译内存取 `max(题目内存, 512MB)`；编译非 `system_error` 失败统一报 `compile_error` |
| 运行命令 | cpp17 `/box/prog/Main`；java21 `java -Xmx<堆上限> -cp /box/prog Main`（堆上限 = 有效内存 − 48MB 非堆预留，下限 16MB）；python `python3.12 /box/prog/Main.py` |
| 标准流 | 逐点独立运行；测试点文件只读挂载作 stdin（零拷贝）；期望输出有文件时按 1MB 分块与 stdout 字节比较（不整份读入内存），仅长度 / 末尾空白不一致时逐行兜底；内联数据按行归一化 |
| 默认比对 | 忽略行尾空白与末尾换行、行内严格 |
| 输出上限 | `--fsize=(上限+1)KB` 内核封顶（超限收 SIGXFSZ）；执行器最多读 `limit+1` 字节 → OLE |
| 沙箱隔离 | 每次运行前清空可写区；作业目录只读挂 `/box/prog`、测试点只读挂 `/box/data`；namespace 隔离 mount / PID / IPC / UTS / net（无网络）；`--processes` 恒下发（编译 64、运行取 `process_limit`——不给时任何 fork 报 EAGAIN）；执行环境注入 `TMPDIR=/tmp`、`HOME=/box`、`PYTHONDONTWRITEBYTECODE=1`、`LANG=C.UTF-8` |
| box 池 | 启动时 `isolate --init --cg` 预建池（最多 8 路并行 `--init`），热路径只跑 `--run`；归还前清空可写区；超时 / meta 缺失 / **OOM 后**均标记不健康、入队由专用线程异步清理重建（不占 case worker）；等不到 box 超 60s 报 `system_error`；启动校验池容量 ≥ `capacity×(case_parallel+1)` 且并发 ≤ CPU 核数（不满足只告警） |
| 挂载点 | `--dir` 不替调用方建目录，执行器每次预建 `/box/prog`、`/box/data`；编译产物拷回后保留可执行位（否则只读挂载后 execve 报 Permission denied） |
| 状态映射 | `status=XX` → system_error；TO / 超限 → TLE；`cg-oom-killed` 或 RSS 超限或 stderr 含 MemoryError/bad_alloc/OutOfMemoryError → MLE；SIGXFSZ 或输出超限 → OLE；RE/SG 或退出码非 0 → runtime_error；否则 ok |

> isolate 失败（box 未初始化 / meta 缺失）时回收重建 box，节点按 `system_error` 回传通用信息，不回传宿主细节。执行器只接绝对路径 argv 数组（直接 execve，不经 `/bin/sh`）。

### 10.12 错误码

`1001` 语言不在白名单 / 代码或输入超 64KB；`3001` 提交或题目不存在；`3002` 状态冲突；`4001` 提交冷却中；`4002` 全局并发上限；`5001` 上游沙箱失败。

### 10.13 通过率口径

练习 / 比赛提交到达终态且 `status <> 'system_error'` 时对 `problem_counters` 累加：`submission_count+1`，AC 再 `accepted_count+1`；**验题与 system_error 不计入**；计数与判题落库同事务。

---

## 11. 社区

### 11.1 表

**`code_shares`**：`user_id` / `title` / `description`（Markdown ≤64KB）/ `language`（`cpp17`/`python3.12`/`java21`）/ `code`（≤64KB）/ `problem_id` / `status`（`published` / `removed`，无草稿态）。索引 INDEX(`status`,`created_at`)、INDEX(`user_id`,`status`)。

**`solutions`**：`problem_id` / `user_id` / `title` / `content`（Markdown ≤64KB）/ `status`（`published` / `removed`）。索引 INDEX(`problem_id`,`status`)、INDEX(`user_id`,`status`)。

**`comments`**：`user_id` / `target_type`（`solution` / `code_share`；CHECK 预留 `problem` / `post` / `submission`）/ `target_id` / `parent_id`（**仅允许挂一级评论**，不提供三级楼中楼）/ `content`（≤2000 字符）/ `is_deleted`。索引 INDEX(`target_type`,`target_id`,`created_at`)、INDEX(`parent_id`)。

**`reports`**：`reporter_id` / `target_type`（`problem` / `solution` / `post` / `comment` / `user`）/ `target_id` / `reason` / `status`（`pending` / `handled` / `ignored`）/ `handled_by` / `handled_at`。索引 INDEX(`status`,`created_at`)。

**`notifications`** / **`messages`** / **`posts`**：规划中，仅建模型未实现端点。

### 11.2 官方题解

官方题解即 `problems.solution`，编辑入口沿用写题向导；本模块只负责**展示**：`GET /problems/{pid}/editorial` 面向可通过题目可见性检查的任何人返回（`can_manage` 随响应返回）。题目详情不再内联渲染官方题解，前端收口到题解页「官方题解」tab。

### 11.3 比赛防作弊门禁

题目被任意**进行中**比赛引用时，该题的全部社区内容（官方题解、分享题解、评论的读与写）一律 `3002`。**全局隐藏**而非仅对参赛者隐藏（非参赛者可见即可转发）。比赛结束后自动开放。

### 11.4 功能开关

`community.feature_switches`（JSONB，缺省键视为开启）：`solutions=false` 拒绝题解写操作；`comments=false` 拒绝评论创建；`codes=false` 拒绝代码分享写操作——**均只影响写，浏览不受影响**，拒绝返回 `3002`。

### 11.5 端点

**题解**：`GET/POST /problems/{pid}/solutions`、`GET/PUT/DELETE /solutions/{id}`。创建直接 `published`，60s 频控 4002；`removed` 态作者不可编辑（恢复走 admin）。

**代码广场**：`GET/POST /codes`、`GET/PUT/DELETE /codes/{id}`。发布无草稿态，60s 冷却；关联题被进行中比赛引用时创建 / 详情 3002、**列表过滤**。

**评论**：`GET/POST /comments`、`DELETE /comments/{id}`。一级评论分页（升序，每条附前 2 条回复 + `reply_count`）；`parent_id=` 取回复分页；3s 频控（按目标 / 父评论隔离）。

**举报**：`POST /reports`（同用户同目标 pending 中重复 3003，60s 频控）。

**管理**：`GET /admin/reports`、`POST /reports/{report_id}/handle`、`GET/PUT /admin/solutions*`、`GET/PUT /admin/comments*`、`GET/PUT /admin/codes*`（见 §12.3）。

### 11.6 数据所有权

- 题目可见性继承：题解 / 评论的一切读写先过题目访问检查，无权用户一律 `2003`（不泄漏存在性）
- 团队快照题沿用裸路径拦截：非 admin 走裸端点 `2003`，团队上下文不提供题解入口
- 软删评论若有未删回复，列表返回占位行（`content=null`、作者置空）；无未删回复则整行隐藏
- 举报人身份不向被举报方暴露；`removed` 内容仅作者与 admin 可读

### 11.7 错误码

`3001` 不存在；`2003` 越权 / 题目不可见；`3002` 比赛门禁 / 开关关闭 / 目标不可评 / removed 态编辑；`3003` 重复举报；`4001`/`4002` 频控。

---

## 12. 管理 / 运维

> 本节端点权限全部为 `admin`。

### 12.1 `system_configs`

KV + 分域（`category`：`site` / `auth_email` / `team` / `contest` / `sandbox` / `log` / `community`）。UNIQUE(`category`,`config_key`)；`updated_by` / `updated_at`。

| 域 | 关键配置 |
| --- | --- |
| site | `site.name` / `logo` / `icp` / `default_theme` / `register_enabled` / `banners`（首页轮播）/ `announcement`（系统公告） |
| auth_email | `email.code.expire_seconds` / `resend_seconds` / `max_attempts`；`email.verify_enabled`；`email.smtp.host/port/username/password/sender/smtp_mode`；`email.template.code_html`（占位符 `{code}` / `{purpose}`） |
| team | `invite.expire_hours`、`team.apply.review_rule` |
| contest | `contest.freeze_default_seconds`、`contest.penalty_factor_minutes` |
| sandbox | `sandbox.judge_concurrency`、`sandbox.cooldown_seconds` |
| log | `log.retention_days`、`log.record_get_logs` |
| community | `community.feature_switches` |

- SMTP `smtp_mode`：`ssl`（465）/ `starttls`（587）/ `plain`（25）；端口 0 时按模式推导。host 为空时开发 / 测试环境打印验证码到日志，**生产返回 `5001`**（不静默失败）
- `*.password` 类配置管理接口一律掩码返回 `******`，提交掩码值视为未修改
- 业务侧实时读库（无缓存），保存即生效

### 12.2 日志表

- **`request_logs`**：`request_id` / `user_id` / `method` / `path` / `status_code` / `ip_address`（解析后真实客户端 IP）/ `user_agent` / `duration_ms` / `extra`（JSONB，沙箱执行子记录按 request_id 归入）。索引 INDEX(`user_id`,`created_at`)、INDEX(`path`,`created_at`)、INDEX(`created_at`,`id`)；进程内有界队列 + 单写协程批量落库（100 条或 200ms，关闭时 drain），队列满时 GET 日志可丢弃、写操作 / 异常日志兜底直写
- **`login_logs`**：`user_id` / `email` / `action`（`login`/`logout`/`register`/`reset_password`/`change_email`）/ IP / UA / `success` / `reason`
- **`exception_logs`**：`level`（`error`/`warning`/`fatal`）/ `message` / `traceback` / `request_id` / `user_id`

> 沙箱执行日志归入 `request_logs.extra`，**不单独建表**；请求体不明文回传（脱敏摘要）。

### 12.3 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /admin/users | 用户列表 |
| GET | /admin/users/lookup | 按邮箱**精确**查找（仅 active，返回最小公开字段） |
| GET | /admin/users/online | 在线面板（10 分钟窗口；同 `user_id + device_info` 去重，每行 = 一台设备） |
| GET | /admin/submissions | 全站提交面板 |
| PUT | /admin/users/{id}/roles | 全局角色授权（**整体替换**唯一角色） |
| POST | /admin/users/{id}/ban、/unban | 封禁 / 解封 |
| POST | /admin/users/{id}/freeze、/unfreeze | 冻结（`duration_minutes` 1–10080，缺省 15）/ 解冻 |
| GET/PUT | /admin/configs | 系统配置（分域） |
| GET | /site-config | 公开站点配置（白名单：name/logo/icp/default_theme/register_enabled/email_verify_enabled/banners/announcement） |
| POST | /files/upload/avatar | 头像（≤2MB，≤10 次/小时） |
| POST | /files/upload/image | 公共图片（≤5MB，≤30 次/小时） |
| POST | /files/upload/site-logo | 站点 Logo（≤5MB，≤10 次/小时） |
| GET | /files/{object_key} | 公开文件读取（仅 `users/` 与 `site/logo/` 前缀；`immutable` 长缓存 + ETag；可选 `?w=96/192/384/640/960/1280` 返回 WebP 缩略图） |
| GET/DELETE | /admin/logs/{type} | 日志查询 / 导出、一键清空（type ∈ request/login/exception） |
| GET | /admin/sandbox/status | 沙箱状态（读 Redis `sandbox:node:<id>`） |
| GET | /admin/reports、POST /reports/{id}/handle | 举报列表 / 处理（`handled` / `ignored`） |
| GET/PUT | /admin/solutions*、/admin/comments*、/admin/codes* | 社区内容治理（下架 / 恢复、软删 / 恢复） |
| 见 §7.7 | /admin/problems/import、/export | FPS 导入 / 导出 |
| 见 §7.7 | /admin/tags* | 标签管理 |
| 见 §5.5、§6.5、§9.3、§8.2 | /admin/orgs*、/admin/teams*、/admin/contests、/admin/problem-sets | 各模块管理视图 |

**图片链路**：非 GIF 上传即转 WebP（质量 82，超宽先缩）；解码前按头部尺寸校验 ≤40MP（上传与按需缩略图共用 2 路信号量）；前端按展示尺寸请求 `?w=` 缩略图；`/api/v1/files/` 带长缓存 + ETag，前端 nginx 对 `/api/v1/files/` 做 30 天边缘缓存。

### 12.4 深分页查询

三张日志表统一「延迟关联 + id 决胜列」：

```sql
SELECT r.* FROM <log_table> r
JOIN (SELECT id FROM <log_table> [WHERE ...]
      ORDER BY created_at DESC, id DESC LIMIT :n OFFSET :m) p ON p.id = r.id
ORDER BY r.created_at DESC, r.id DESC
```

子查询走覆盖索引只取主键（Index Only Scan），深页代价只随索引深度增长；`id` 决胜列保证翻页不重不漏；API 契约不变（page / page_size + 精确 total）。

### 12.5 错误码

`2003` 非 admin；`3001` 用户 / 配置 / 日志不存在；`1001` 配置值格式错误。

---

## 13. 附录：实现状态与明确不做

### 13.1 实现状态

| 模块 | 状态 |
| --- | --- |
| users / files / orgs / teams / problems / problem-sets / contests / judge / community / admin | 已实现（端点与数据模型如上） |
| 组织化改造（组织实体 / 组织题库 / 团队引用来源切换 / tutor 下线） | 已实现 |
| 判题链路（gRPC 网关 + isolate 节点 + 维护循环 + SPJ + 用户自测） | 已实现 |
| 通知 / 私信 / 讨论区（`notifications` / `messages` / `posts`） | 仅建模型，端点未实现 |
| 团队加入审批通知 | 未实现 |
| AI 能力（AI 改码 / 纠错 / 出题） | 暂缓，契约与依赖已摘除 |

### 13.2 明确不做

**全局**

- 不引入 WebSocket / SSE 实时推送（榜单前端轮询）
- 不引入 Celery / 外部消息队列（判题用进程内 asyncio gRPC 网关）
- 不引入子任务 / 分组加权计分（总分 = 通过测试点分值之和）
- 不建权限表（`permissions` / `role_permissions`）——功能权限应用层按角色 code 分支
- 不做 per-problem 语言级限制覆盖（C++ 基准 + 全局语言比例）
- 不建独立沙箱日志表 / 独立验题判题表（归 `request_logs.extra` / 复用 `submissions`）
- 不用 Kubernetes / Docker Swarm；业务实体统一 PostgreSQL，Redis 只放短生命周期数据

**用户**：不做第三方 OAuth；不做邮箱解绑；注销后数据不物理删除

**组织**：不做邀请链接 / 加入申请审批；不建组织角色表；组织题不进题库中心；跨组织不互通；不设组织级题单 / 比赛

**团队**：邀请链接不设撤销 / 人数 / 一次性限制；不建团队角色表；解散后资源归档不物理删除

**题库**：不物理删除题目；团队题不设「升级公开」通道；SPJ 仅 C++17 单文件（不支持部分分 / 多文件 / 数据生成器）；测试点不向前端暴露下载 / 预签名 URL；难度分不自动校准；通过率不落库为比率字段

**题单**：不物理删除，下线走 archived；团队题单不进题单中心

**比赛**：运行中题目不锁定；不做实时榜单推送；不允许迟交 / 补交（但允许赛后补题）；不引入 OI / 子任务赛制

**判题**：沙箱默认禁网且不提供例外开关；不提供用户可控 URL 执行接口；**后端进程不执行任何用户代码**；特判程序不跨作业缓存二进制、不回传编译错误 / stderr

**社区**：评论不物理删除；不做三级楼中楼；不做点赞与排序；不做独立管理后台评论列表页；团队快照题不提供题解 / 评论
