# 架构与规范

> 本文档合并了技术栈、分层架构、编码规范、前端约定、安全规则与权限设计。AI 写代码前先读本文件。

## 技术栈

| 类别 | 选型 | 版本 | 备注 |
| --- | --- | --- | --- |
| 后端框架 | FastAPI | - | 组织 REST 接口 |
| 数据访问 | SQLAlchemy ORM + Alembic | - | Alembic 管理迁移 |
| 异步任务 | Celery | - | 判题 / AI 出题 / 定时任务 |
| AI 编排 | LangGraph | - | 编排 AI 工作流 |
| 模型调用 | LiteLLM | - | 统一封装模型提供方 |
| 数据库 | PostgreSQL | 16 | |
| 缓存 / 队列 | Redis | 7 | 会话、邀请链接、限流、Celery 队列 |
| 对象存储 | MinIO | - | 测试点、头像、图片 |
| 代码沙箱 | nsjail | - | 进程级隔离，限制 CPU / 内存 / 时间 / 进程 / 文件系统 |
| 前端 | Vue 3 + Pinia + Element Plus + Tailwind CSS | - | Tailwind v4 辅助布局（见 `docs/decisions/2026-08-17-frontend-tailwind.md`） |
| 代码编辑器 | Monaco Editor | - | |
| 部署 | Docker Compose | - | |

## 明确不使用的技术

以下技术流行但本项目刻意不用，AI 不得引入：

- **WebSocket / SSE 实时推送** — 榜单前端采用轮询刷新（如 5s 间隔），不做实时推送
- **子任务 / 分组加权计分** — 题目测试点分值一致，总分 = 通过测试点分值之和，不引入 OI / 子任务模型
- **per-problem 语言级限制覆盖** — 题目限制以 C++ 为基准，其他语言统一按 `sandbox_configs` 全局语言比例换算，不做每题语言覆盖表（见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
- **独立沙箱日志表 / 独立验题判题表** — 沙箱执行日志作为 `request_logs.extra` 子记录，验题判题复用 `submissions`，均不单独建表
- **权限表（`permissions` / `role_permissions`）** — 功能权限不落表，应用层按角色 code 分支判定
- **Kubernetes / Docker Swarm** — 用 Docker Compose，沙箱可横向扩容
- **把本地 nsjail Docker 编排直接当生产方案** — 本地验证编排使用 `privileged`，生产必须改为受控节点、最小 capability 与任务级资源配置
- **NoSQL 存储业务实体** — 业务实体统一 PostgreSQL；Redis 只放短生命周期数据（邀请链接、会话热点、限流计数、沙箱节点状态）

## 分层架构

```text
Route → Service → Repository → Database
  └──────────────┴────────────→ Shared（横切：错误类、响应信封、日志、RBAC 中间件）
```

| 层 | 职责 | 绝对不能做 |
| --- | --- | --- |
| Route | 解析 HTTP 请求，鉴权 / 权限中间件，调用 Service，返回响应 | ❌ 业务逻辑、SQL |
| Service | 业务规则、校验、编排、RBAC 权限分支，调用 Repository | ❌ 直接操作数据库、处理 HTTP 细节 |
| Repository | 封装数据访问（SQLAlchemy），返回业务对象 | ❌ 业务判断 |
| Shared | 响应信封、错误类、日志、RBAC 中间件、配置 | ❌ 依赖业务模块 |

依赖方向永远向下；Shared 可被任意层引用。模块间只通过 Service 通信，不得跨模块直接访问对方 Repository。

## 代码组织（按领域模块分包）

```text
src/backend/
  app/
    main.py                    # FastAPI 应用入口
    worker.py                  # Celery 应用（worker + beat 任务）
    shared/                    # 响应信封 · 错误类 · RBAC 中间件 · 日志 · 配置
    modules/
      auth/                    # 注册 / 登录 / 会话
      users/                   # 用户中心 / 用户管理
      teams/                   # 团队 / 成员 / 申请 / 邀请
      problems/                # 题库 / 测试点 / 验题
      problem_sets/            # 题单
      contests/                # 比赛 / 报名 / 榜单
      judge/                   # 提交 / 判题调度
      sandbox/                 # 沙箱配置 / 节点
      ai/                      # 聊天 / 改码 / 编译纠错 / 出题
      community/               # 通知 / 消息 / 题解 / 帖子 / 评论 / 举报
      admin/                   # 系统配置 / 日志 / 模型配置
```

- 每个模块包含 `routes.py` / `service.py` / `repository.py` / `models.py`（SQLAlchemy 模型）/ `schemas.py`（Pydantic）
- 迁移文件集中在 `alembic/versions/`；表结构唯一来源是迁移 SQL，契约文件中的表结构是其文档化说明

## 模块

| 模块 | 职责 | 主要实体 | 对外能力 |
| --- | --- | --- | --- |
| 认证 / 用户中心 | 注册登录、账号生命周期、偏好 | `users`、`user_sessions` | 注册 / 登录 / 找回密码 / 会话管理 / 资料设置 |
| 用户管理 | 全局角色授权、封禁、Token 用量 | `user_roles`、`user_token_stats` | 角色调整 / 封禁 / 用量查询 |
| 团队 | 团队、邀请、成员、角色 | `teams`、`team_members`、`team_member_applications` | 建队 / 邀请 / 审批 / 成员管理 / 解散 |
| 题库 | 公开 / 团队题目统一管理 | `problems`、`test_cases`、`problem_tags`、验题表 | 题目 CRUD、可见性控制、验题、样例 / 测试点管理 |
| 题单 | 公开 / 团队题单 | `problem_sets`、`problem_set_items` | 题单 CRUD、题目编排 |
| 比赛 | 公开 / 团队比赛、报名、榜单 | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings` | 建赛 / 报名 / 提交 / 榜单 / 封榜 |
| 判题 | 提交、调度、判题结果 | `submissions`、`submission_test_case_results` | 提交判题、历史查询 |
| 沙箱 | nsjail 安全执行器；由 Judge Worker 调用，不直接承载公网业务 API | `sandbox_configs` | 编译 / 运行 / 资源限制 / 健康检查 |

> 判题采用 Codeforces 风格的「调度器 → Judge Worker → nsjail 执行器」链路。Judge Worker 负责从内部存储准备代码与测试点到本地临时目录，沙箱不访问 MinIO、数据库或公网。
| AI | 聊天、改码、编译纠错、出题、Token 统计 | `ai_conversations`、`ai_messages`、`ai_requests`、`user_token_stats`、`ai_generation_tasks` | AI 能力接入、用量统计 |
| 社区 | 通知、消息、题解、讨论、评论、举报 | `notifications`、`messages`、`solutions`、`posts`、`comments`、`reports` | 社区互动 |
| 系统配置 | 站点 / 认证 / 团队 / 比赛 / 模型 / 沙箱 / 日志 / 社区配置 | `system_configs`、`model_configs`、`sandbox_configs` | 配置管理 |
| 运维 | 日志、状态 | `request_logs`、`login_logs`、`exception_logs` | 日志查询 / 导出 / 异常追踪 |

## 编码规范

### 命名

| 对象 | 规范 | 示例 |
| --- | --- | --- |
| 文件 / 目录 | snake_case | `problem_service.py` |
| 类 | PascalCase | `ProblemService` |
| 函数 / 变量 | snake_case | `create_problem` |
| 常量 | UPPER_SNAKE_CASE | `MAX_CODE_BYTES` |
| 数据库表 / 列 | snake_case 复数表名 | `problems`、`user_id` |
| API 路径 | kebab-case 复数名词 | `/api/v1/problem-sets` |

### Python 规则

- 模型字段、校验 Schema 遵循 `docs/contracts/` 数据模型（迁移 SQL 为唯一来源）
- 枚举字段使用 `VARCHAR(n)` + CHECK 约束（SQLAlchemy 侧可用 `Enum`）；状态 / 可见性语义见对应契约文件
- 空值用 `None` 表示「无」
- 每个 Service 方法单一职责；模块间只通过 Service 调用

### 错误处理

- 错误必须使用 `docs/contracts/common.md` 定义的错误码段（`10xx` / `20xx` / `30xx` / `40xx` / `50xx`）与模块专属码
- 数据库错误在 Repository 层转换为业务错误；Service 层不得直接抛驱动错误
- API 响应不暴露堆栈跟踪、敏感信息（测试点期望输出、模型 Key、沙箱内部路径）

### 数据访问与迁移

- 表结构变更必须创建 Alembic 迁移（up/down）；迁移 SQL 是表结构唯一来源
- 循环外键（`problems.ai_generation_task_id` ↔ `ai_generation_tasks.problem_id`）分两步迁移：先建一侧外键，初始化后 `ALTER TABLE` 补齐另一侧
- 查询显式列出所需列，不用 `SELECT *`
- 所有用户数据查询必须带 `WHERE user_id = ?`（数据所有权，见各契约文件）

## 前端约定

- 页面级组件管理状态（Pinia），展示型组件纯渲染
- 前端用户可见文案通过 vue-i18n 管理，默认中文并支持 English 切换；上传统一走 `src/api/files.ts`
- **国际化要求**：所有面向用户的静态文案（页面、组件、路由标题、菜单、表格列、表单标签/占位符、空状态、弹窗、通知、导出表头及展示字典）必须使用 `src/i18n/` 中的 key，不得在 Vue/TS 中硬编码自然语言；新增或修改文案时必须同时提供 `zh-CN` 与 `en-US` 翻译。服务端返回的业务错误信息可按原样展示，但前端兜底错误提示必须国际化。
- 每个数据视图覆盖 loading / error / empty / success 四种状态
- 通过统一 API 层调用后端，统一处理响应信封 `{ code, message, data }`
- 整体布局：左侧边栏为**固定 76px 图标栏（收缩态，悬浮显示名称提示）**，**用户菜单在顶栏右上角**（头像下拉进入个人资料 / 安全设置 / 会话管理 / 管理后台）；顶栏左上角以**面包屑**展示当前定位，只反映真实层级（如 `管理后台/用户管理`、`题库/题目详情`），首页与顶级区块互相平级不入面包屑，不设返回按钮；右侧为顶栏 + 内容区，**区块（路由下 ≥2 个子页）时在内容区顶部自动渲染二级菜单栏**（如用户设置），区块子页仅 1 个时不显示。**管理后台是独立工作空间**：从前台不可见侧栏入口（仅头像菜单进入），进入后侧栏整体切换为管理菜单（用户/配置/日志/沙箱/举报），共用同一布局外壳
- 路由权限：菜单与路由按 `meta.roles` 过滤（管理后台仅 `admin`），路由守卫做登录 / 角色校验（见 `docs/architecture.md` 权限设计）
- **样式约定**：组件样式归 Element Plus；页面布局 / 间距 / 排版用 Tailwind CSS v4 原子类（`dark:` 变体与 EP `html.dark` 暗色策略对齐），见 `docs/decisions/2026-08-17-frontend-tailwind.md`
- 题目样例提供「复制 / 一键填入」入口：用户可将样例输入一键填入编辑器输入框，通过测试样例接口运行
- 写题界面左半展示题目内容并可切换 AI 聊天窗口，右半为 Monaco 编辑器
- AI 修改代码必须展示 diff 等用户确认后应用，前端不得直接覆盖编辑器代码

## 安全规则

- 代码执行仅在 nsjail 沙箱进行，限制 CPU / 内存 / 时间 / 进程 / 文件系统，并限制输出大小、磁盘配额、CPU 核数；沙箱默认禁止网络访问（禁外网 / 禁内网元数据）
- 密码、会话 Token 哈希存储；邮箱验证码存 Redis（短 TTL，不落库）；模型 API Key 加密存储
- 判题测试点文件仅判题服务内部可读，不向前端暴露下载 / 预签名 URL；提交结果不返回期望输出
- AI 修改代码必须用户确认后应用，避免自动覆盖用户代码
- 全部资源访问按 RBAC + 资源级可见性双重校验
- 提交限频：按用户 + 题目提交冷却 + 全局判题并发上限（Redis 频控）；提交代码大小上限 64KB（UTF-8 字节）
- 文件上传：统一文件 Service 写入 MinIO；对象 key 由服务端生成（不信任客户端路径），类型白名单，大小上限（头像 ≤2MB、测试点 / SPJ ≤16MB）；前端通过统一 multipart 上传工具调用文件接口
- 不硬编码密钥 / token / 密码 / URL；不在日志记录敏感信息

## 权限设计（RBAC）

### 角色与作用域

| 作用域 | 角色 code | 说明 |
| --- | --- | --- |
| global | `admin` | 系统管理员 |
| global | `tutor` | 导师 |
| global | `user` | 普通用户（默认） |
| team | `team_creator` | 团队创建者 |
| team | `team_admin` | 团队管理员 |
| team | `team_member` | 团队成员 |

- 统一由 `roles`（静态种子）+ `user_roles`（运行时授权）承载；`scope` 标定生效范围（global/team），`object_id` 标定生效对象（global 为 NULL，team 为团队 id）
- 功能权限不落表（无 `permissions` / `role_permissions`），由中间件装载角色后按角色 `code` 在应用层分支判定
- `team_creator` 权限集 ⊇ `team_admin`（创建者默认拥有团队管理员全部权限，额外含「分配管理员」）
- 团队角色仅在团队资源上下文（`scope='team'`、`object_id=<team_id>`）叠加判定
- 资源级可见性（题目 / 题单 / 比赛）由查询层按 `owner_id / team_id / visibility` 过滤，不依赖权限表
- 接口权限列直接标注角色 code（逗号分隔），如 `admin/tutor/team_creator/team_admin`；`public` = 无需登录，`auth` = 登录即可，`owner` = 资源所有者本人（或团队内对应角色）

### 角色职责（种子）

| 角色 | 职责 |
| --- | --- |
| `admin` | 全部能力：用户管理、系统配置、运维、公开比赛、团队、AI 出题等 |
| `tutor` | 创建团队、创建公开比赛、管理题目、使用 AI（含出题） |
| `user` | 浏览题目 / 题单 / 比赛、提交、AI 聊天 / 改代码 / 编译纠错（默认角色） |
| `team_creator` | 团队内全部管理：邀请 / 成员 / 题库 / 题单 / 比赛 / AI 出题，含「分配管理员」 |
| `team_admin` | 同 `team_creator`，但不含「分配管理员」 |
| `team_member` | 查看团队题单 / 比赛、提交、AI 聊天 |

### 权限矩阵

| 功能 | 用户 | 导师 | 系统管理员 | 团队创建者 | 团队管理员 |
| --- | --- | --- | --- | --- | --- |
| 用户中心 | 是 | 是 | 是 | 是 | 是 |
| 用户管理 | 否 | 否 | 是 | 否 | 否 |
| 创建团队 | 否 | 是 | 是 | 否 | 否 |
| 生成团队邀请链接 | 否 | 否 | 否 | 是 | 是 |
| 分配团队管理员 | 否 | 否 | 否 | 是 | 否 |
| 管理团队题单 | 否 | 否 | 否 | 是 | 是 |
| 管理团队题库 | 否 | 否 | 否 | 是 | 是 |
| 创建团队比赛 | 否 | 否 | 否 | 是 | 是 |
| 创建公开比赛 | 否 | 是 | 是 | 否 | 否 |
| 查看公开比赛 | 是 | 是 | 是 | 是 | 是 |
| 查看所在团队比赛 | 是 | 是 | 是 | 是 | 是 |
| 系统配置 | 否 | 否 | 是 | 否 | 否 |
| 查看运维面板 | 否 | 否 | 是 | 否 | 否 |
| 使用代码编辑器 | 是 | 是 | 是 | 是 | 是 |
| 使用 AI 能力 | 是 | 是 | 是 | 是 | 是 |
| 使用 AI 出题工具 | 否 | 是 | 是 | 是 | 是 |

> 团队创建者、团队管理员是团队内角色，可与全局角色叠加；团队创建者默认拥有团队管理员的全部权限。

## 缓存与异步设计

### Redis 使用点（Key 约定）

| Key | 说明 | TTL |
| --- | --- | --- |
| `team:invite:<token>` | 团队邀请链接 → {team_id} | 链接有效期（默认配置） |
| `session:<token>` | 会话热点缓存 | 会话有效期 |
| `email:code:<email>:<purpose>` | 邮箱验证码 + 错误计数（不落库） | 验证码有效期（默认配置） |
| `email:resend:<email>:<purpose>` | 验证码重发间隔计数 | 重发间隔（默认配置） |
| `rank:contest:<id>` | 榜单热数据（前端轮询刷新，不做 WebSocket/SSE） | 比赛期 |
| `sandbox:node:<id>` | 沙箱节点运行时状态（在线 / 负载 / 健康检查） | 心跳周期（过期视为离线） |
| `submit:cooldown:<user_id>:<problem_id>` | 提交冷却计数（存在即冷却中，过期视为可提交） | 冷却时长（默认配置，如 10s） |
| `judge:global:running` | 全局判题并发计数（原子增减，达上限时排队或拒绝） | 判题期（TTL 兜底防泄漏） |

> 缓存一致性：会话、邀请链接、沙箱节点状态为 Redis 唯一事实来源，不落库；榜单以数据库 `contest_rankings` 为权威数据，Redis 仅作读缓存，失效 / 封榜切换时回源数据库。

### Celery 任务清单

| 任务 | 说明 | 触发 |
| --- | --- | --- |
| `judge_submission` | 判题执行（参数：submission_id） | 提交时 |
| `run_sample` | 样例执行（内联） | 接口调用 |
| `ai_generate_problem` | AI 出题 | 出题请求 |
| `aggregate_token_stats` | Token 用量按天汇总 → `user_token_stats` | 定时 / 增量 |
| `contest_transition` | 比赛状态推进：封榜置 `board_frozen` + 冻结榜单行；结束解封、重算、置 `finished` | 定时（每分钟扫描） |
| `contest_unfreeze` | 解封并重算榜单 | 定时 / 按需 |
| `sandbox_health_check` | 周期健康检查，异常节点剔除并重调度任务 | 定时 |
| `sandbox_autoscale` | 按负载自动扩缩容沙箱实例 | 定时 |
| `cleanup_expired` | 清理过期会话（验证码由 Redis TTL 自动过期） | 定时 |

### MinIO 存储规范

| 对象 key | 说明 |
| --- | --- |
| `problems/{problem_id}/cases/{case_id}/input` | 判题测试点输入 |
| `problems/{problem_id}/cases/{case_id}/output` | 判题测试点期望输出 |
| `submissions/{submission_id}/cases/{case_id}/output` | 提交运行输出 |
| `users/{user_id}/avatar` | 用户头像 |
| `teams/{team_id}/avatar` | 团队头像 |

> 上传方式：文件经 `POST /files/upload` 由后端校验后转存 MinIO，对象 key 由服务端按上表规范生成并回填 ossId；测试点 / SPJ 文件上传仅题目管理角色可调。判题节点使用独立只读账号，将测试点拉取到沙箱宿主机本地目录，沙箱进程不直连 MinIO；测试点对象不向前端签发预签名 URL。

## 可观测性

- `request_logs`：全量请求（含 `request_id` 追踪）；沙箱执行日志作为子记录按 `request_id` 归入 `extra`
- `ai_requests` + `user_token_stats`：AI 调用与 Token 用量
- `login_logs`、`exception_logs`：安全与异常
