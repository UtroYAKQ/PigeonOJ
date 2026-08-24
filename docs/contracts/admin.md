# 管理 / 运维模块契约

> 系统配置、模型配置、用户管理（角色 / 封禁 / Token 用量）、日志。所有端点权限为 `admin`。

## 数据模型

### `system_configs` — 系统配置表

KV + 分域，承载站点 / 认证 / 团队 / 比赛 / 沙箱 / 日志 / 社区等全部可配置项。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| category | VARCHAR(32) | NOT NULL | `site` / `auth_email` / `team` / `contest` / `model` / `token` / `sandbox` / `log` / `community` |
| config_key | VARCHAR(128) | NOT NULL | 配置键，如 `site.name`、`invite.expire_hours` |
| config_value | JSONB | NOT NULL | 配置值 |
| description | TEXT | NULL | 配置说明 |
| updated_by | UUID | NULL, FK → users.id | 最近修改人 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`category`, `config_key`)

配置项举例（非穷举）：

| 域 | 配置键（示例） | 说明 |
| --- | --- | --- |
| site | `site.name` / `site.logo` / `site.icp` / `site.default_theme` | 站点基础配置 |
| site | `site.register_enabled` | 注册开关 |
| auth_email | `email.code.expire_seconds` / `email.code.resend_seconds` / `email.code.max_attempts` | 验证码安全策略 |
| auth_email | `email.verify_enabled` | 注册邮箱验证开关（false 时注册无需验证码） |
| auth_email | `email.smtp.host` / `port` / `username` / `password` / `sender` / `use_ssl` | SMTP 发信配置；host 为空时验证码打印到后端日志（本地开发兜底）。`*.password` 类键管理接口一律掩码返回（`******`），提交掩码值视为未修改 |
| team | `invite.expire_hours` | 邀请链接默认有效期 |
| team | `team.apply.review_rule` | 加入审批规则 |
| contest | `contest.freeze_default_seconds` / `contest.penalty_factor_minutes` | 封榜 / 罚时系数默认 |
| model | `token.stat_scope` | Token 统计口径 |
| sandbox | `sandbox.judge_concurrency` / `sandbox.cooldown_seconds` | 全局并发上限 / 提交冷却 |
| log | `log.retention_days` | 日志保留时间 |
| community | `community.feature_switches` | 社区功能开关 |

### `model_configs` — 大模型配置表

结构见 [ai.md](ai.md)（`admin` 管理，API Key 加密存储）。

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

索引：INDEX(`user_id`, `created_at`)、INDEX(`path`, `created_at`)、INDEX(`created_at`)

> 沙箱执行日志（判题 / 编译 / 运行 / AI 编译纠错）作为请求链路的子记录写入 `extra`，以 `request_id` 关联归入同一请求行，不单独建沙箱日志表。本表以 `created_at` 为前导列，按时间分页 / 保留清理。

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

索引：INDEX(`user_id`, `created_at`)、INDEX(`created_at`)

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

索引：INDEX(`created_at`)、INDEX(`level`, `created_at`)

## 数据所有权

- 所有端点仅 `admin` 可调
- 日志查询支持按时间范围 / 条件筛选与导出；日志不外泄请求体明文（`request_logs.extra` 为脱敏摘要）
- 用户 Token 用量查看基于 `user_token_stats` 聚合（不暴露请求明细）
- 模型 API Key 加密存储，管理接口不回传明文

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /admin/users | admin | 用户列表 | 分页/关键字/状态 | user[] |
| PUT | /admin/users/{id}/roles | admin | 全局角色授权（写 `user_roles` scope='global'） | role_ids | - |
| POST | /admin/users/{id}/ban | admin | 封禁（违规 / 异常，仅可人工解封） | reason | - |
| POST | /admin/users/{id}/unban | admin | 解封 | - | - |
| POST | /admin/users/{id}/freeze | admin | 冻结（与安全策略同款，立即拦截登录；可人工解冻） | reason | - |
| POST | /admin/users/{id}/unfreeze | admin | 解冻 | - | - |
| GET/PUT | /admin/configs | admin | 系统配置（分域） | - | - |
| GET | /site-config | public | 公开站点配置（白名单字段：name / logo / icp / default_theme / register_enabled / email_verify_enabled；前端壳层与注册页消费） | - | siteConfig |
| POST | /files/upload/avatar | auth | 上传当前用户头像到 MinIO | multipart file（≤2MB，JPG/PNG/WEBP/GIF） | oss_id / url |
| GET | /files/{object_key} | public | 读取头像等公开文件；不允许读取测试点 | object_key（仅 users/ 前缀） | binary |
| GET/PUT | /admin/models | admin | 大模型配置 | - | - |
| GET | /admin/token-stats | admin | 用户 Token 用量统计 | 分页 | stat[] |
| GET | /admin/logs/{type} | admin | 日志查询 / 筛选 / 导出 | 时间范围/条件 | log[] |
| GET | /admin/sandbox/status | admin | 沙箱状态展示（读 Redis） | - | nodes[] |
| GET | /admin/reports | admin | 举报列表 / 处理 | 分页/状态 | report[] |

> **实现状态**：`GET/PUT /admin/models` 与 `GET /admin/token-stats` 随 AI 模块暂缓实现（当前未提供对应端点与表结构），其余端点已实现。

> **账号状态语义**：`frozen`（冻结：安全策略自动触发或管理员手动冻结，可到期自动解冻或人工解冻）与 `banned`（封禁：管理员主动封禁，仅可人工解封）均拦截登录；区分见 `users.md`「账号状态语义」。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 2003 | 403 | 非 `admin` 访问管理端点 |
| 3001 | 404 | 用户 / 配置 / 日志不存在 |
| 1001 | 400 | 配置值格式 / 类型错误 |

## 关键流程 / 验收条件

1. **全局角色授权**：`PUT /admin/users/{id}/roles` 写 `user_roles`（`scope='global'`、`object_id=NULL`）；全局角色部分唯一索引兜底防重复。
2. **封禁 / 解封、冻结 / 解冻**：写 `users.status`（`banned` / `frozen`），均立即拦截登录；`frozen` 可到期自动解冻，`banned` 仅人工解封。
3. **系统配置**：按 `category` 分域读写 `system_configs`；修改人记录 `updated_by`。业务侧实时读库（无缓存），保存后立即生效；已接线消费方：`auth_email` 验证码策略 / 注册邮箱验证开关 / SMTP 发信、`sandbox` 冷却 / 并发、`site.register_enabled` 注册开关、`site` 公开展示字段（经 `/site-config`）。
4. **日志**：`request_logs`（含沙箱子记录）、`login_logs`、`exception_logs` 按条件查询 / 导出。

## 明确不做

- 文件上传由服务端校验类型 / 大小并生成对象 key；头像对象使用 `users/{user_id}/avatar/{uuid}`，测试点对象不暴露下载 / 预签名 URL（判题内部链路）
- 日志请求体不回传明文（脱敏摘要）
- Token 用量仅统计、不做额度控制
