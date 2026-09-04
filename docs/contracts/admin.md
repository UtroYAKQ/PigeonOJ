# 管理 / 运维模块契约

> 系统配置、用户管理（角色 / 封禁）、日志。所有端点权限为 `admin`。

## 数据模型

### `system_configs` — 系统配置表

KV + 分域，承载站点 / 认证 / 团队 / 比赛 / 沙箱 / 日志 / 社区等全部可配置项。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| category | VARCHAR(32) | NOT NULL | `site` / `auth_email` / `team` / `contest` / `sandbox` / `log` / `community` |
| config_key | VARCHAR(128) | NOT NULL | 配置键，如 `site.name`、`invite.expire_hours` |
| config_value | JSONB | NOT NULL | 配置值 |
| description | TEXT | NULL | 配置说明 |
| updated_by | UUID | NULL, FK → users.id | 最近修改人 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`category`, `config_key`)

配置项举例（非穷举）：

| 域 | 配置键（示例） | 说明 |
| --- | --- | --- |
| site | `site.name` / `site.logo` / `site.icp` / `site.default_theme` | 站点基础配置。`site.logo` 值为站内文件 URL（`/api/v1/files/site/logo/{uuid}`，经 `POST /files/upload/site-logo` 上传）或 http(s) 外链；空则前端回退默认图标 |
| site | `site.register_enabled` | 注册开关 |
| auth_email | `email.code.expire_seconds` / `email.code.resend_seconds` / `email.code.max_attempts` | 验证码安全策略 |
| auth_email | `email.verify_enabled` | 注册邮箱验证开关（false 时注册无需验证码） |
| auth_email | `email.smtp.host` / `port` / `username` / `password` / `sender` / `smtp_mode` | SMTP 发信配置。`smtp_mode` 取值 `ssl`（隐式 TLS）/ `starttls`（明文后升级）/ `plain`（明文，仅内网）；端口未显式配置（`email.smtp.port=0`）时按模式自动推导：`ssl=465` / `starttls=587` / `plain=25`，设正数则视为显式覆盖。`use_ssl`（旧键）已废弃，存在 `smtp_mode` 时忽略。host 为空且为生产环境时直接报错（不再静默兜底）；开发/测试环境将验证码打印到后端日志便于联调。`*.password` 类键管理接口一律掩码返回（`******`），提交掩码值视为未修改 |
| auth_email | `email.template.code_html` | 验证码邮件 HTML 正文模板（管理员可编辑的美化卡片）。占位符 `{code}` = 验证码、`{purpose}` = 用途文案（取自固定枚举：注册 / 重置密码 / 修改邮箱）。留空使用内置默认卡片。后端同时附带纯文本兜底，模板中必须保留 `{code}` 否则邮件无验证码。 |
| team | `invite.expire_hours` | 邀请链接默认有效期 |
| team | `team.apply.review_rule` | 加入审批规则 |
| contest | `contest.freeze_default_seconds` / `contest.penalty_factor_minutes` | 封榜 / 罚时系数默认 |
| sandbox | `sandbox.judge_concurrency` / `sandbox.cooldown_seconds` | 全局并发上限 / 提交冷却 |
| log | `log.retention_days` / `log.record_get_logs` | 日志保留时间；是否记录 GET 请求日志（默认 true，关闭后中间件跳过 GET 只记写操作；10s 进程内缓存） |
| community | `community.feature_switches` | 社区功能开关 |

### `request_logs` — 请求日志表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| request_id | VARCHAR(64) | NOT NULL | 全链路追踪 ID |
| user_id | UUID | NULL, FK → users.id | |
| method | VARCHAR(8) | NOT NULL | |
| path | VARCHAR(512) | NOT NULL | |
| status_code | INT | NOT NULL | |
| ip_address | INET | NULL | |
| user_agent | TEXT | NULL | |
| duration_ms | INT | NULL | |
| extra | JSONB | NULL | 扩展字段（沙箱执行子记录：语言 / 判定 / 耗时 / 内存等，按 request_id 归入本行） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `created_at`)、INDEX(`path`, `created_at`)、INDEX(`created_at`, `id`)

> 沙箱执行日志（判题 / 编译 / 运行）作为请求链路的子记录写入 `extra`，以 `request_id` 关联归入同一请求行，不单独建沙箱日志表。本表以 `created_at` 为前导列，按时间分页 / 保留清理。`ip_address` 为解析后的真实客户端 IP（X-Forwarded-For 左起首个公网段，见 `docs/operations.md`）；每条响应回传 `X-Request-Id` 响应头供排障关联。

### `login_logs` — 登录日志表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NULL, FK → users.id | |
| email | VARCHAR(255) | NULL | 失败登录时兜底记录 |
| action | VARCHAR(32) | NOT NULL | `login` / `logout` / `register` / `reset_password` / `change_email` |
| ip_address | INET | NULL | |
| user_agent | TEXT | NULL | |
| success | BOOLEAN | NOT NULL | |
| reason | VARCHAR(255) | NULL | 失败原因 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `created_at`)、INDEX(`created_at`, `id`)

### `exception_logs` — 异常日志表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| level | VARCHAR(16) | NOT NULL | `error` / `warning` / `fatal` |
| message | TEXT | NOT NULL | |
| traceback | TEXT | NULL | |
| request_id | VARCHAR(64) | NULL | 关联请求 |
| user_id | UUID | NULL, FK → users.id | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`created_at`, `id`)、INDEX(`level`, `created_at`)

### 深分页查询约定

三张日志表的分页查询统一采用**延迟关联 + id 决胜列**（`LogRepository._page`）：

```sql
SELECT r.* FROM <log_table> r
JOIN (SELECT id FROM <log_table> [WHERE ...]
      ORDER BY created_at DESC, id DESC LIMIT :n OFFSET :m) p ON p.id = r.id
ORDER BY r.created_at DESC, r.id DESC
```

- 子查询按 `(created_at, id)` 覆盖索引仅取主键（Index Only Scan），OFFSET 丢弃的行不回表，深页代价只随索引深度增长；外层仅回表页内行
- `id` 为决胜列：同 `created_at` 行的全序固定，翻页不重复 / 不漏行
- API 契约不变：仍为 page / page_size + 精确 total

## 数据所有权

- 所有端点仅 `admin` 可调
- 日志查询支持按时间范围 / 条件筛选与导出；日志不外泄请求体明文（`request_logs.extra` 为脱敏摘要）

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /admin/users | admin | 用户列表 | 分页/关键字/状态 | user[] |
| PUT | /admin/users/{id}/roles | admin | 全局角色授权（**单一角色模型**：整体替换该用户唯一全局角色，写 `user_roles` scope='global'） | role_id | - |
| POST | /admin/users/{id}/ban | admin | 封禁（违规 / 异常，仅可人工解封） | reason | - |
| POST | /admin/users/{id}/unban | admin | 解封 | - | - |
| POST | /admin/users/{id}/freeze | admin | 冻结（立即拦截登录；人工解冻） | reason | - |
| POST | /admin/users/{id}/unfreeze | admin | 解冻 | - | - |
| GET/PUT | /admin/configs | admin | 系统配置（分域） | - | - |
| GET | /site-config | public | 公开站点配置（白名单字段：name / logo / icp / default_theme / register_enabled / email_verify_enabled；前端壳层与注册页消费） | - | siteConfig |
| POST | /files/upload/avatar | auth | 上传当前用户头像到 MinIO | multipart file（≤2MB，JPG/PNG/WEBP/GIF） | oss_id / url |
| POST | /files/upload/image | auth | 公共图片上传（题面插图等 Markdown 引用场景，登录用户可用），存 MinIO `users/{uid}/images/` | multipart file（≤5MB，JPG/PNG/WEBP/GIF） | oss_id / url |
| POST | /files/upload/site-logo | admin | 站点 Logo 上传（站点配置 `site.logo` 引用），存 MinIO `site/logo/` | multipart file（≤5MB，JPG/PNG/WEBP/GIF） | oss_id / url |
| GET | /files/{object_key} | public | 读取头像 / 公共图片 / 站点 Logo 等公开文件；不允许读取测试点 | object_key（仅 `users/` 或 `site/logo/` 前缀） | binary |
| GET | /admin/logs/{type} | admin | 日志查询 / 筛选 / 导出（keyword：request=请求号/路径，login=邮箱/动作，exception=消息/堆栈；nickname：按用户昵称模糊过滤，经 `users.nickname` 关联，与 keyword 可叠加） | 分页/keyword/nickname/时间范围 | log[] |
| DELETE | /admin/logs/{type} | admin | 一键清空指定类型日志（全表删除，危险操作；type ∈ request / login / exception，非法值 3001） | - | - |
| GET | /admin/sandbox/status | admin | 沙箱状态展示（读 Redis `sandbox:node:<id>`；指标由网关心跳写入） | - | nodes[{id, name, status, channel, load, cpu_usage, memory_usage, running_tasks, capacity, version, last_heartbeat_at}] |
| GET | /admin/reports | admin | 举报列表 / 处理 | 分页/状态 | report[] |

> **实现状态**：上表端点均已实现。

> **账号状态语义**：`frozen`（冻结：管理员手动冻结，人工解冻）与 `banned`（封禁：管理员主动封禁，仅可人工解封）均拦截登录；登录失败超次为 Redis 临时锁定（到期自动恢复），不涉及账号状态。区分见 `users.md`「账号状态语义」。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 2003 | 403 | 非 `admin` 访问管理端点 |
| 3001 | 404 | 用户 / 配置 / 日志不存在 |
| 1001 | 400 | 配置值格式 / 类型错误 |

## 关键流程 / 验收条件

1. **全局角色授权**：`PUT /admin/users/{id}/roles` 写 `user_roles`（`scope='global'`、`object_id=NULL`）；**单一角色模型**——每个用户恰好持有一个全局角色（`admin` / `tutor` / `user`），授权为整体替换而非叠加；唯一索引兜底防重复。
2. **封禁 / 解封、冻结 / 解冻**：写 `users.status`（`banned` / `frozen`），均立即拦截登录；`frozen` 可到期自动解冻，`banned` 仅人工解封。
3. **系统配置**：按 `category` 分域读写 `system_configs`；修改人记录 `updated_by`。业务侧实时读库（无缓存），保存后立即生效；已接线消费方：`auth_email` 验证码策略 / 注册邮箱验证开关 / SMTP 发信、`sandbox` 冷却 / 并发、`site.register_enabled` 注册开关、`site` 公开展示字段（经 `/site-config`）。
4. **日志**：`request_logs`（含沙箱子记录）、`login_logs`、`exception_logs` 按条件查询 / 导出。

## 明确不做

- 文件上传由服务端校验类型 / 大小并生成对象 key；头像对象使用 `users/{user_id}/avatar/{uuid}`，站点 Logo 使用 `site/logo/{uuid}`，测试点对象不暴露下载 / 预签名 URL（判题内部链路）
- 日志请求体不回传明文（脱敏摘要）
- Token 用量仅统计、不做额度控制
