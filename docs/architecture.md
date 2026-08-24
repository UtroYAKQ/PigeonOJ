# 架构与规范

> 本文档合并了技术栈、分层架构、编码规范、前端约定、安全规则与权限设计。AI 写代码前先读本文件。

## 技术栈

| 类别 | 选型 | 版本 | 备注 |
| --- | --- | --- | --- |
| 后端框架 | FastAPI | - | 组织 REST 接口 |
| 数据访问 | SQLAlchemy ORM + Alembic | - | Alembic 管理迁移 |
| 判题节点网关 | gRPC（双向流） | - | 节点注册 / 心跳 / 派题 / 回传结果；取代早期 Celery 方案（见 `docs/decisions/2026-08-23-grpc-judge-gateway.md`） |
| AI 编排 | LangGraph | - | 编排 AI 工作流（AI 模块暂缓实现，依赖按需安装） |
| 模型调用 | LiteLLM | - | 统一封装模型提供方（AI 模块暂缓实现，依赖按需安装） |
| 数据库 | PostgreSQL | 16 | |
| 缓存 | Redis | 7 | 会话热点、邀请链接、限流、判题节点心跳状态 |
| 对象存储 | MinIO | - | 测试点、头像、图片 |
| 代码沙箱 | nsjail | - | 进程级隔离，限制 CPU / 内存 / 时间 / 进程 / 文件系统 |
| 前端 | Vue 3 + Pinia + Naive UI + Tailwind CSS | - | Tailwind v4 辅助布局（见 `docs/decisions/2026-08-17-frontend-tailwind.md`、`docs/decisions/2026-08-24-naive-ui-nova-style.md`） |
| 代码编辑器 | Monaco Editor | - | |
| 部署 | Docker Compose | - | |

## 明确不使用的技术

以下技术流行但本项目刻意不用，AI 不得引入：

- **WebSocket / SSE 实时推送** — 榜单前端采用轮询刷新（如 5s 间隔），不做实时推送
- **Celery / 外部消息队列** — 判题采用进程内 asyncio gRPC 推送网关（见 `docs/decisions/2026-08-23-grpc-judge-gateway.md`），不引入 broker；比赛推进等周期任务随对应模块以进程内调度实现
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
  └──────────────┴────────────→ Shared（横切：错误类、响应信封、日志、平台配置）
```

| 层 | 职责 | 绝对不能做 |
| --- | --- | --- |
| Route | 解析 HTTP 请求，鉴权 / 权限中间件，调用 Service，返回响应 | ❌ 业务逻辑、SQL |
| Service | 业务规则、校验、编排、RBAC 权限分支，调用 Repository | ❌ 直接操作数据库、处理 HTTP 细节 |
| Repository | 封装数据访问（SQLAlchemy），返回业务对象 | ❌ 业务判断 |
| Shared | 响应信封、错误类、日志、基础设施客户端、平台表（系统配置 / 审计日志） | ❌ 依赖业务模块 |

依赖方向永远向下且无环（见 `docs/decisions/2026-08-24-backend-module-packaging.md`）：

- **Shared 不依赖任何业务模块**；`system_configs` 与审计日志三表是平台表，模型与读写助手在 `shared/infra/`，admin 模块只提供其管理端点
- **跨模块只允许 import 对方包的 `api.py`**（唯一出口），其余文件视为私有；ORM 模型可经 `api.py` 再导出供跨模块查询
- 每张业务表只有一个归属模块；其他模块引用外键 id 或调用属主的 api 钩子函数回写状态，不直接改对方表的行
- 路由所在包不必与 URL 前缀一一对应（如 `POST /problems/{id}/verify` 在 judge 包注册）
- 以上规则由 `src/backend/scripts/check_import_rules.py` 机械检查（用法见 `docs/operations.md`）

> 架构定位：按领域分包的分层模块化单体（Service Layer + Repository 模式），非 DDD。不变量复杂的局部（判题状态机、比赛状态推进）可在属主模块内引入充血模型，不要求全面转向。

## 代码组织（按领域模块分包）

```text
src/backend/
  backend.toml               # 后端配置文件（app/config.py 加载；.env / 环境变量可覆盖）
  app/
    main.py                    # FastAPI 应用入口（组合根；lifespan 内启动判题 gRPC 网关与维护循环）
    config.py                  # 配置加载（backend.toml + .env / 环境变量覆盖）
    shared/                    # 纯技术设施，不依赖业务模块
      infra/                   # 数据库 · Redis · MinIO · 日志 · 平台表（system_config.py / audit.py）
      auth/security.py         # 密码哈希 · Token 工具
      common/                  # 响应信封 · 错误类 · 分页 · 校验
    modules/                   # 每个模块含 api.py 对外门面；跨模块只准 import 它
      users/                   # 认证 / 用户中心 / 用户管理 / RBAC 判定（已实现）
      files/                   # 文件上传（MinIO；已实现）
      problems/                # 题库 / 测试点 / 验题记录（已实现；题单规划并入此模块）
      judge/                   # 提交 / 验题提交 / 判题调度 / 沙箱配置 / gRPC 节点网关（已实现）
      admin/                   # 系统配置与日志管理端点 / 举报处理（已实现）
      teams/                   # 团队 / 成员 / 申请 / 邀请（骨架）
      contests/                # 比赛 / 报名 / 榜单（骨架）
      ai/                      # 聊天 / 改码 / 编译纠错 / 出题（骨架；暂缓实现）
      community/               # 通知 / 消息 / 题解 / 帖子 / 评论 / 举报（骨架）
```

- 已实现模块包含 `api.py`（对外门面，唯一出口）/ `routes.py` / `service.py` / `repository.py` / `models.py`（SQLAlchemy 模型）/ `schemas.py`（Pydantic），可选 `deps.py` / `permissions.py`；骨架模块仅保留 `__init__.py`
- 迁移文件集中在 `alembic/versions/`；表结构唯一来源是迁移 SQL，契约文件中的表结构是其文档化说明

## 模块

| 模块 | 职责 | 主要实体 | 对外能力 |
| --- | --- | --- | --- |
| 认证 / 用户中心 / 用户管理（users） | 注册登录、账号生命周期、偏好、全局角色授权、封禁、RBAC 判定 | `users`、`user_sessions`、`roles`、`user_roles`、`user_token_stats` | 注册 / 登录 / 找回密码 / 会话管理 / 资料设置 / 角色调整 / 封禁 / 用量查询 |
| 团队（teams） | 团队、邀请、成员、角色 | `teams`、`team_members`、`team_member_applications` | 建队 / 邀请 / 审批 / 成员管理 / 解散 |
| 题库（problems） | 公开 / 团队题目统一管理（含题单规划） | `problems`、`test_cases`、`problem_tags`、`problem_verifications`、验题邀请表 | 题目 CRUD、可见性控制、验题记录、样例 / 测试点管理 |
| 题单（并入 problems） | 公开 / 团队题单 | `problem_sets`、`problem_set_items` | 题单 CRUD、题目编排 |
| 比赛（contests） | 公开 / 团队比赛、报名、榜单 | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings` | 建赛 / 报名 / 提交 / 榜单 / 封榜 |
| 判题（judge） | 提交 / 验题提交 / 判题调度（gRPC 节点网关） | `submissions`、`submission_test_case_results`、`sandbox_configs` | 提交判题、验题代码提交、历史查询、节点健康 |
| AI（ai） | 聊天、改码、编译纠错、出题、Token 统计 | `ai_conversations`、`ai_messages`、`ai_requests`、`user_token_stats`、`ai_generation_tasks` | AI 能力接入、用量统计 |
| 社区（community） | 通知、消息、题解、讨论、评论、举报 | `notifications`、`messages`、`solutions`、`posts`、`comments`、`reports` | 社区互动 |
| 系统配置 / 运维（admin） | 站点 / 认证 / 团队 / 比赛 / 模型 / 沙箱 / 日志 / 社区配置的管理端点，日志查询，举报处理 | 管理端点覆盖平台表（`system_configs` 与日志三表模型在 shared/infra）、`reports`、`model_configs` | 配置管理、日志查询 / 导出、异常追踪、举报处理 |
| 运维 | 日志、状态 | `request_logs`、`login_logs`、`exception_logs` | 日志查询 / 导出 / 异常追踪 |

> 判题采用 Codeforces 风格的「后端 gRPC 网关 → 判题节点 → nsjail 执行器」链路：网关维护节点注册表并按负载派发作业，判题节点容器经双向流接收作业、按 `data_version` 经 `FetchProblemData` 拉取测试点到本地缓存后在 nsjail 内执行，结果沿流回传落库；**后端进程不执行任何用户代码**，沙箱不访问 MinIO、数据库或公网（见 `docs/contracts/judge.md`）。

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
- 每个 Service 方法单一职责；跨模块只 import 对方 `api.py` 门面（见分层架构与 `docs/decisions/2026-08-24-backend-module-packaging.md`）

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
- **工程化门禁**：ESLint（`eslint.config.js`）+ Prettier（`.prettierrc.json`）+ Vitest（jsdom 环境）；
  变更提交前须过 `npm run lint:check` / `npm test` / `npm run build`（命令见 `docs/operations.md`，约定见 `docs/frontend.md`）
- 前端用户可见文案通过 vue-i18n 管理，默认中文并支持 English 切换；上传统一走 `src/api/files.ts`
- **国际化要求**：所有面向用户的静态文案（页面、组件、路由标题、菜单、表格列、表单标签/占位符、空状态、弹窗、通知、导出表头及展示字典）必须使用 `src/i18n/` 中的 key，不得在 Vue/TS 中硬编码自然语言；新增或修改文案时必须同时提供 `zh-CN` 与 `en-US` 翻译。服务端返回的业务错误信息可按原样展示，但前端兜底错误提示必须国际化。
- 每个数据视图覆盖 loading / error / empty / success 四种状态
- 通过统一 API 层调用后端，统一处理响应信封 `{ code, message, data }`
- 整体布局：左侧边栏为**可折叠菜单栏（展开 220px / 收起 64px 图标态，悬浮显示名称提示）**，**用户菜单在顶栏右上角**（头像下拉进入个人资料 / 安全设置 / 会话管理 / 管理后台）；顶栏左侧为折叠钮与**面包屑**，只反映真实层级（如 `管理后台/用户管理`、`题库/题目详情`），首页与顶级区块互相平级不入面包屑。**管理后台是独立工作空间**：从前台不可见侧栏入口（仅头像菜单进入），进入后侧栏整体切换为管理菜单（用户/配置/日志/沙箱/举报），共用同一布局外壳
- 路由权限：菜单与路由按 `meta.roles` 过滤（管理后台仅 `admin`），路由守卫做登录 / 角色校验（见 `docs/architecture.md` 权限设计）
- **样式约定**：组件样式归 Naive UI（主题经 `settings/theme.ts` 注入）；页面布局 / 间距 / 排版用 Tailwind CSS v4 原子类（`dark:` 变体与 `html.dark` 暗色策略对齐），见 `docs/decisions/2026-08-17-frontend-tailwind.md`、`docs/decisions/2026-08-24-naive-ui-nova-style.md`
- 题目样例提供「复制输入」入口；在线试运行能力规划由判题节点侧专用端点承担（后端进程不执行用户代码，见 `docs/contracts/judge.md`）
- 规划：写题界面左半展示题目内容并可切换 AI 聊天窗口，右半为 Monaco 编辑器（随 AI 模块实现）
- AI 修改代码必须展示 diff 等用户确认后应用，前端不得直接覆盖编辑器代码

## 安全规则

- 代码执行仅在 nsjail 沙箱进行，限制 CPU / 内存 / 时间 / 进程 / 文件系统，并限制输出大小、磁盘配额、CPU 核数；沙箱默认禁止网络访问（禁外网 / 禁内网元数据）
- 密码、会话 Token 哈希存储；邮箱验证码存 Redis（短 TTL，不落库）；模型 API Key 加密存储
- 判题测试点文件仅判题服务内部可读，不向前端暴露下载 / 预签名 URL；提交结果不返回期望输出
- AI 修改代码必须用户确认后应用，避免自动覆盖用户代码
- 全部资源访问按 RBAC + 资源级可见性双重校验
- 提交限频：按用户 + 题目提交冷却（Redis）+ 全局判题并发上限（网关注册表内存统计）；提交代码大小上限 64KB（UTF-8 字节）
- 文件上传：统一文件 Service 写入 MinIO；对象 key 由服务端生成（不信任客户端路径），类型白名单，大小上限（头像 ≤2MB、测试点 ≤16MB）；前端通过统一 multipart 上传工具调用文件接口
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
| `sandbox:node:<id>` | 判题节点运行时状态（在线 / 负载 / 心跳），由网关心跳桥接写入 | 心跳周期（过期视为离线） |
| `judge:cooldown:<user_id>:<problem_id>` | 提交冷却计数（存在即冷却中，过期视为可提交） | 冷却时长（默认配置，如 10s） |
| `judge:requeue:<submission_id>` | 维护循环重派互斥锁（SETNX 防并发重复投递） | 重派窗口 |

> 缓存一致性：会话、邀请链接、判题节点状态为 Redis 唯一事实来源，不落库；榜单以数据库 `contest_rankings` 为权威数据，Redis 仅作读缓存，失效 / 封榜切换时回源数据库。全局判题并发上限由网关注册表在内存中统计（节点 in-flight 之和），不占用 Redis。

### 后台调度机制（无 Celery / 无独立 worker 进程）

| 机制 | 说明 | 现状 |
| --- | --- | --- |
| gRPC 网关派发 | `dispatch_submission` 按 in-flight 最少优先选节点，`build_job_bundle` 原子认领后沿双向流推送作业；无在线节点保持 `pending` | 已实现（随应用 lifespan 启动） |
| 网关维护循环 | 每 30s 扫描超时提交（judging 过久重置 pending 重派、断线节点 in-flight 回收） | 已实现 |
| 节点心跳桥接 | 上行 Heartbeat → 写 Redis `sandbox:node:<id>`，供管理后台沙箱状态页展示 | 已实现 |
| 比赛状态推进（`contest_transition`：封榜 / 解封 / 结束重算） | 按比赛时间周期推进 | 随 contests 模块实现 |
| Token 用量按天汇总（`aggregate_token_stats` → `user_token_stats`） | 增量聚合 AI 用量 | 随 AI 模块实现（暂缓） |

> 以上周期机制均以进程内 asyncio 循环实现（与网关同生命周期），不引入 Celery 或外部队列。

### MinIO 存储规范

| 对象 key | 说明 |
| --- | --- |
| `problems/{problem_id}/cases/{case_id}/input` | 判题测试点输入 |
| `problems/{problem_id}/cases/{case_id}/output` | 判题测试点期望输出 |
| `submissions/{submission_id}/cases/{case_id}/output` | 提交运行输出 |
| `users/{user_id}/avatar` | 用户头像 |
| `teams/{team_id}/avatar` | 团队头像 |

> 上传方式：文件经 `POST /files/upload` 由后端校验后转存 MinIO，对象 key 由服务端按上表规范生成并回填 ossId；测试点文件上传仅题目管理角色可调。**判题节点不访问 MinIO**：经网关认证后按 `data_version` 流式拉取测试点到节点本地缓存（容器 `/cache`），沙箱进程不直连对象存储；测试点对象不向前端签发预签名 URL。

## 可观测性

- `request_logs`：全量请求（含 `request_id` 追踪）；沙箱执行日志作为子记录按 `request_id` 归入 `extra`
- `ai_requests` + `user_token_stats`：AI 调用与 Token 用量
- `login_logs`、`exception_logs`：安全与异常
