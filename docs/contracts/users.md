# 认证 / 用户模块契约

> 用户账号、注册登录、会话与账号生命周期。功能权限见 `docs/security.md`。

## 数据模型

### `users` — 用户表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| email | VARCHAR(255) | NOT NULL, UNIQUE | 登录邮箱 |
| email_verified | BOOLEAN | NOT NULL DEFAULT false | 注册邮箱是否已验证 |
| password | VARCHAR(255) | NOT NULL | 密码（bcrypt/argon2 哈希存储，不存明文） |
| nickname | VARCHAR(64) | NOT NULL | 昵称 |
| avatar_url | VARCHAR(512) | NULL | 头像：站内完整文件 URL（`/api/v1/files/users/{uid}/avatar/{uuid}`，即 `POST /files/upload/avatar` 返回的 `url`）或可信外链 `http(s)://…`；前端直接渲染，无需再拼接前缀 |
| signature | VARCHAR(255) | NULL | 个性签名 |
| theme | VARCHAR(32) | NOT NULL DEFAULT 'light' | 页面主题样式偏好 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` 正常 / `frozen` 冻结 / `banned` 封禁 / `deleted` 已注销 |
| last_login_at | TIMESTAMPTZ | NULL | 最近登录时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：

- UNIQUE(`email`)
- INDEX(`status`)

### 邮箱验证码（存 Redis，不落库）

验证码是短时效数据，不建数据库表，由 Redis 存储：

- 验证码 key：`email:code:<email>:<purpose>`（存验证码与错误计数），TTL = 配置的 `email.code.expire_seconds`
- 重发间隔计数：`email:resend:<email>:<purpose>`，TTL = 配置的 `email.code.resend_seconds`
- 一次性使用：校验通过后删除 `email:code:*` key；错误超次删除并触发频控（Key 约定见 `docs/operations.md` Redis 约定）
- 安全策略（有效期 / 重发间隔 / 最大尝试）配置见 `docs/contracts/admin.md` 的 `auth_email` 配置域

### `user_sessions` — 登录会话表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 所属用户 |
| token | VARCHAR(64) | NOT NULL, UNIQUE | 会话 Token（哈希存储） |
| device_info | VARCHAR(255) | NULL | 设备标识 |
| ip_address | INET | NULL | 登录 IP |
| user_agent | TEXT | NULL | 浏览器 UA |
| expires_at | TIMESTAMPTZ | NOT NULL | 会话过期时间 |
| revoked_at | TIMESTAMPTZ | NULL | 撤销时间（非空即已撤销） |
| last_active_at | TIMESTAMPTZ | NULL | 最近活跃时间 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `expires_at`, `revoked_at`)

## 数据所有权

- 用户只能读写自己的资料与会话：所有相关 SQL 必须带 `WHERE user_id = ?`（当前登录用户）
- 注销为软注销：`status='deleted'`，`email` 替换为脱敏值（如 `u<id>@invalid.local`）以释放邮箱并保持唯一约束
- 会话撤销仅本人可执行（`owner`）
- 返回用户对象必须排除 `password` 字段

## 账号状态语义

| 状态 | 触发 | 恢复 | 登录 |
| --- | --- | --- | --- |
| `active` | 正常 | — | 允许 |
| `frozen` 冻结 | 管理员手动冻结（登录失败超次不冻结，改为 Redis 临时锁定） | 人工解冻 | 拦截 |
| `banned` 封禁 | 管理员对违规 / 异常账号主动封禁 | 仅可人工解封 | 拦截 |
| `deleted` 注销 | 用户主动注销 | 不可恢复 | 拒绝 |

> 冻结不涉及违规定性；封禁为管理员主动行为。两者均拦截登录，管理接口见 `admin.md`。

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /auth/email-code | public | 发送验证码 | email, purpose | - |
| POST | /auth/register | public | 注册 | email, code（邮箱验证开启时必填）, password, nickname | - |
| POST | /auth/login | public | 登录 | email, password | token, user |
| POST | /auth/logout | auth | 登出 | - | - |
| POST | /auth/reset-password | public | 重置密码 | email, code, new_password | - |
| POST | /auth/change-password | auth | 修改密码 | old_password, new_password | - |
| POST | /auth/change-email | auth | 换绑邮箱 | new_email, code | - |
| GET | /users/me | auth | 当前用户 | - | user |
| PUT | /users/me | auth | 更新资料 | nickname/signature/theme/avatar_url（头像存站内完整文件 URL `/api/v1/files/users/{uid}/avatar/…`——前端直接使用 `POST /files/upload/avatar` 返回的 `url`——或可信外链 `http(s)://…`；不接受裸 `oss_id`；替换时 best-effort 删除被替换的站内旧头像对象） | user |
| POST | /files/upload/avatar | auth | 上传头像（频控 ≤10 次/小时/用户，超次 4002） | multipart file，≤2MB，JPG/PNG/WEBP/GIF | url（站内文件 URL） |
| DELETE | /users/me | auth | 注销账号（软注销） | password | - |
| GET | /users/me/sessions | auth | 会话列表 | - | session[] |
| DELETE | /users/me/sessions/{sid} | owner | 注销指定会话 | - | - |

> 用户管理（角色授权 / 封禁）端点见 `admin.md`。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 1001 | 400 | 邮箱 / 密码 / 昵称格式错误 |
| 2001 | 401 | 未登录 |
| 2002 | 401 | 会话已过期 |
| 2004 | 401 | 验证码错误 / 密码错误 / Token 无效 |
| 2005 `REGISTER_DISABLED` | 403 | 站点未开放注册（`site.register_enabled=false`；校验先于验证码消费） |
| 3002 | 409 | 邮箱已注册 / 账号已冻结或封禁 |
| 4001 | 429 | 验证码发送过频（重发间隔内） |
| 4002 | 429 | 登录失败超次触发临时锁定（不改动账号状态，锁定到期自动恢复） |

## 关键流程 / 验收条件

1. **注册**：`POST /auth/email-code`（purpose=register）→ 用户收码 → `POST /auth/register` 校验通过后创建 `users`（`email_verified=true`），验证码从 Redis 删除（一次性）。站点关闭注册（`site.register_enabled=false`）时返回 `2005` 且不消耗验证码；关闭邮箱验证（`email.verify_enabled=false`）时无需验证码直接注册。
2. **登录**：校验密码 + 会话写入 `user_sessions` + Redis 热点缓存；登录失败超次触发临时锁定（Redis `login:lock:*`，15 分钟内拒绝全部登录尝试，到期自动恢复；不改动账号状态，管理员手动冻结仍走 admin 接口）。
3. **找回密码**：`email-code`（purpose=reset_password）→ `reset-password` 重置。
4. **换绑邮箱**：`email-code`（purpose=change_email）→ `change-email`。
5. **会话管理**：登出 / 注销指定会话时 `revoked_at` 置位，同步清 Redis 缓存。

## 明确不做

- 不提供第三方 OAuth 登录（当前仅邮箱 + 密码）
- 不做邮箱解绑（换绑仅替换邮箱）
- 注销后数据不物理删除（软注销；用户数据按业务规则归档）
