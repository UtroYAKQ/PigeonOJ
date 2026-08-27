# 架构与规范

> 本文档合并了技术栈、分层架构、编码规范、前端约定、安全规则与权限设计。AI 写代码前先读本文件。

## 技术栈

| 类别 | 选型 | 版本 | 备注 |
| --- | --- | --- | --- |
| 后端框架 | FastAPI | - | 组织 REST 接口 |
| 数据访问 | SQLAlchemy ORM + Alembic | - | Alembic 管理迁移 |
| 判题节点网关 | gRPC（双向流） | - | 节点注册 / 心跳 / 派题 / 回传结果；取代早期 Celery 方案（见 `docs/decisions/2026-08-23-grpc-judge-gateway.md`） |
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
api/v1（路由）→ services（业务）→ repositories（仓储）→ models → Database
                    └────────────→ core（横切：数据库 / Redis / 存储 / 异常 / 依赖注入 / 日志）
                                    rpc（判题网关基础设施：gRPC 服务 · 节点注册 · 巡检；gen/ 为生成代码）
                                    utils（纯工具：安全 · 响应信封 · 分页 · 校验）　enums（全局枚举常量）
```

| 层 | 目录 | 职责 | 绝对不能做 |
| --- | --- | --- | --- |
| 路由层 | `app/api/v1/` | 解析 HTTP 请求，声明鉴权依赖，调用服务，返回响应信封 | ❌ 业务逻辑、SQL |
| 业务层 | `app/services/` | 业务规则、校验、编排、RBAC 分支（组合仓储完成） | ❌ 处理 HTTP 细节、手写 SQL 细节 |
| 仓储层 | `app/repositories/` | 数据访问（SQLAlchemy 纯 CRUD）+ 审计日志写入助手 | ❌ 业务规则分支 |
| 判题网关基础设施 | `app/rpc/` | gRPC 网关服务、节点注册表、负载均衡派发、巡检循环（`gen/` 为生成代码勿手改） | ❌ 处理 HTTP 细节 |
| 模型层 | `app/models/` | ORM 表模型（按资源域拆分文件，聚合包统一注册 metadata） | ❌ 依赖 services / repositories / rpc / api |
| 契约层 | `app/schemas/` | Pydantic 请求 / 响应模型 | ❌ 依赖 services / repositories / rpc / api |
| 枚举层 | `app/enums/` | 全局枚举常量（按业务域拆分，聚合包再导出），不 import 任何应用层 | ❌ 依赖任何应用层 |
| 核心设施 | `app/core/` | database / redis / storage / exceptions / dependency / middlewares / log / init_app | — |
| 工具层 | `app/utils/` | security / response / pagination / validation 纯函数 | ❌ 依赖 api / services / repositories / rpc / models / schemas |

依赖方向永远向下且无环（见 `docs/decisions/2026-08-24-backend-layered-restructure.md`
与 `docs/decisions/2026-08-25-backend-service-repository-split.md`）：

- **`app/api/**` 是最上层**：任何非 api 层 import `app.api` 即违规（路由不可被下穿依赖）
- **models / schemas 不依赖 services / repositories / rpc**；平台表（`system_configs` 与审计日志三表）模型在 `models/system_config.py`、`models/audit.py`，服务在 `services/system_config.py`、写入助手在 `repositories/audit.py`，admin 只提供管理端点
- **enums 与 utils 保持纯净**：enums 不 import 其他应用分层；utils 不 import api / services / repositories / rpc / models / schemas（允许 core，如 validation 复用 core.exceptions 错误定义）
- 组合根只有两处允许装配全图：`app/__init__.py`（create_app 工厂）与 `app/core/init_app.py`（路由注册）；认证依赖在 `core/dependency.py`（允许引用 repositories 做会话校验）
- 以上规则由 `src/backend/scripts/check_import_rules.py` 机械检查（用法见 `docs/operations.md`）

> 架构定位：按技术层分包的分层单体，目录结构对齐 vue-fastapi-admin 模板。业务域仍按资源域拆分 service / repository / model / contract 文件（user.py / problem.py / judge.py…）；不变量复杂的局部（判题状态机、比赛状态推进）可在属主 service 内引入充血模型，不要求全面转向。

## 代码组织（按技术层分包）

```text
src/backend/
  run.py                      # 开发启动入口（uvicorn app:app --reload）
  backend.toml                # 后端配置文件（app/settings/config.py 加载；.env / 环境变量可覆盖）
  app/
    __init__.py               # create_app() 应用工厂（组合根；lifespan 内启动判题 gRPC 网关与维护循环）
    settings/config.py        # 配置加载（backend.toml + .env / 环境变量覆盖）
    api/v1/                   # 路由层（每资源一个文件 + base.py 系统端点）
      base.py users.py files.py problems.py judge.py admin.py
    services/                 # 业务逻辑层：<resource>.py = Service 类（组合仓储）
      user.py file.py problem.py judge.py tag.py admin.py system_config.py
    repositories/             # 数据访问仓储层：<resource>.py = Repository 类（纯 CRUD）+ audit 写入助手
      user.py problem.py judge.py admin.py system_config.py audit.py
    rpc/                      # 判题网关基础设施：judge_gateway.py judge_jobs.py
      gen/                      # gRPC 生成代码（scripts/gen_proto.py 产出，勿手改）
    enums/                    # 全局枚举常量（user.py problem.py judge.py audit.py…，__init__ 再导出）
    models/                   # ORM 模型（__init__.py 聚合注册全部表到 Base.metadata）
      user.py audit.py system_config.py problem.py judge.py admin.py
    schemas/                  # Pydantic 契约（user.py file.py problem.py judge.py admin.py common.py）
    core/                     # 数据库 · Redis · MinIO · 异常 · 认证依赖 · 中间件 · 日志 · 应用初始化
    utils/                    # 密码哈希 / Token · 响应信封 · 分页 · 校验（纯工具）
```

- service 文件 = 该资源域的业务 Service 类；repository 文件 = 数据访问类（如 `services/user.py` 含 `UserService / AuthService`，`repositories/user.py` 含 `UserRepository / SessionRepository / RoleRepository`）
- 迁移文件集中在 `alembic/versions/`；表结构唯一来源是迁移 SQL，契约文件中的表结构是其文档化说明

## 模块

| 模块 | 职责 | 主要实体 | 对外能力 |
| --- | --- | --- | --- |
| 认证 / 用户中心 / 用户管理（users） | 注册登录、账号生命周期、偏好、全局角色授权、封禁、RBAC 判定 | `users`、`user_sessions`、`roles`、`user_roles` | 注册 / 登录 / 找回密码 / 会话管理 / 资料设置 / 角色调整 / 封禁 |
| 团队（teams） | 团队、邀请、成员、角色 | `teams`、`team_members`、`team_member_applications` | 建队 / 邀请 / 审批 / 成员管理 / 解散 |
| 题库（problems） | 公开 / 团队题目统一管理（含题单规划） | `problems`、`test_cases`、`problem_tags`、`problem_verifications`、验题邀请链接（Redis） | 题目 CRUD、可见性控制、验题记录、样例 / 测试点管理 |
| 题单（并入 problems） | 公开 / 团队题单 | `problem_sets`、`problem_set_items` | 题单 CRUD、题目编排 |
| 比赛（contests） | 公开 / 团队比赛、报名、榜单 | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings` | 建赛 / 报名 / 提交 / 榜单 / 封榜 |
| 判题（judge） | 提交 / 验题提交 / 判题调度（gRPC 节点网关） | `submissions`、`submission_test_case_results`、`sandbox_configs` | 提交判题、验题代码提交、历史查询、节点健康 |
| 社区（community） | 通知、消息、题解、讨论、评论、举报 | `notifications`、`messages`、`solutions`、`posts`、`comments`、`reports` | 社区互动 |
| 系统配置 / 运维（admin） | 站点 / 认证 / 团队 / 比赛 / 沙箱 / 日志 / 社区配置的管理端点，日志查询，举报处理 | 管理端点覆盖平台表（`system_configs` 与日志三表模型在 `models/`、服务在 `services/system_config.py`、写入助手在 `repositories/audit.py`）、`reports` | 配置管理、日志查询 / 导出、异常追踪、举报处理 |
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
- 每个 Service 方法单一职责；跨模块只 import 对方 service / repository 的公开类与函数（见分层架构与 `docs/decisions/2026-08-25-backend-service-repository-split.md`）

### 错误处理

- 错误必须使用 `docs/contracts/common.md` 定义的错误码段（`10xx` / `20xx` / `30xx` / `40xx` / `50xx`）与模块专属码
- 数据库错误在 Repository 层转换为业务错误；Service 层不得直接抛驱动错误
- API 响应不暴露堆栈跟踪、敏感信息（测试点期望输出、沙箱内部路径）

### 数据访问与迁移

- 表结构变更必须创建 Alembic 迁移（up/down）；迁移 SQL 是表结构唯一来源
- 查询显式列出所需列，不用 `SELECT *`
- 所有用户数据查询必须带 `WHERE user_id = ?`（数据所有权，见各契约文件）

## 前端约定

- 页面级组件管理状态（Pinia），展示型组件纯渲染
- **工程化门禁**：ESLint（`eslint.config.js`）+ Prettier（`.prettierrc.json`）+ Vitest（jsdom 环境）；
  变更提交前须过 `npm run lint:check` / `npm test` / `npm run build`（命令见 `docs/operations.md`，约定见 `docs/frontend.md`）
- 前端用户可见文案通过 vue-i18n 管理，默认中文并支持 English 切换；上传统一走 `src/frontend/src/api/files.ts`
- **国际化要求**：所有面向用户的静态文案（页面、组件、路由标题、菜单、表格列、表单标签/占位符、空状态、弹窗、通知、导出表头及展示字典）必须使用 `src/i18n/` 中的 key，不得在 Vue/TS 中硬编码自然语言；新增或修改文案时必须同时提供 `zh-CN` 与 `en-US` 翻译。服务端返回的业务错误信息可按原样展示，但前端兜底错误提示必须国际化。
- 每个数据视图覆盖 loading / error / empty / success 四种状态
- 通过统一 API 层调用后端，统一处理响应信封 `{ code, message, data }`
- 整体布局：左侧边栏为**可折叠菜单栏（展开 220px / 收起 64px 图标态，悬浮显示名称提示）**，**用户菜单在顶栏右上角**（头像下拉进入个人资料 / 安全设置 / 会话管理 / 管理后台）；顶栏左侧为折叠钮与**面包屑**，只反映真实层级（如 `管理后台/用户管理`、`题库/题目详情`），首页与顶级区块互相平级不入面包屑。**管理后台是独立工作空间**：从前台不可见侧栏入口（仅头像菜单进入），进入后侧栏整体切换为管理菜单（用户/配置/日志/沙箱/举报/标签），共用同一布局外壳
- 路由权限：菜单与路由按 `meta.roles` 过滤（管理后台仅 `admin`），路由守卫做登录 / 角色校验（见 `docs/architecture.md` 权限设计）
- **样式约定**：组件样式归 Naive UI（主题经 `settings/theme.ts` 注入）；页面布局 / 间距 / 排版用 Tailwind CSS v4 原子类（`dark:` 变体与 `html.dark` 暗色策略对齐），见 `docs/decisions/2026-08-17-frontend-tailwind.md`、`docs/decisions/2026-08-24-naive-ui-nova-style.md`
- 题目样例提供「复制输入」入口；用户自测（「自测运行 / 自测输入 / 运行结果」控制台面板）内嵌题目详情页编辑器下方，经判题节点一次性运行，不计分不入提交记录（见 `docs/contracts/judge.md` 用户自测）

## 安全规则

- 代码执行仅在 nsjail 沙箱进行，限制 CPU / 内存 / 时间 / 进程 / 文件系统，并限制输出大小、磁盘配额、CPU 核数；沙箱默认禁止网络访问（禁外网 / 禁内网元数据）
- 密码、会话 Token 哈希存储；邮箱验证码、验题邀请链接存 Redis（短 TTL，不落库）
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
| `admin` | 全部能力：用户管理、系统配置、运维、公开比赛、团队等 |
| `tutor` | 创建团队、创建公开比赛、管理题目 |
| `user` | 浏览题目 / 题单 / 比赛、提交（默认角色） |
| `team_creator` | 团队内全部管理：邀请 / 成员 / 题库 / 题单 / 比赛，含「分配管理员」 |
| `team_admin` | 同 `team_creator`，但不含「分配管理员」 |
| `team_member` | 查看团队题单 / 比赛、提交 |

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

> 团队创建者、团队管理员是团队内角色，可与全局角色叠加；团队创建者默认拥有团队管理员的全部权限。

## 缓存与异步设计

### Redis 使用点（Key 约定）

| Key | 说明 | TTL |
| --- | --- | --- |
| `team:invite:<token>` | 团队邀请链接 → {team_id} | 链接有效期（默认配置） |
| `verify_invite:{token}` | 验题邀请链接 → {"problem_id": "..."}（见 problems.md，不建表） | 链接有效期（发起时指定小时数） |
| `session:<token>` | 会话热点缓存 | 会话有效期 |
| `email:code:<email>:<purpose>` | 邮箱验证码 + 错误计数（不落库） | 验证码有效期（默认配置） |
| `email:resend:<email>:<purpose>` | 验证码重发间隔计数 | 重发间隔（默认配置） |
| `rank:contest:<id>` | 榜单热数据（前端轮询刷新，不做 WebSocket/SSE） | 比赛期 |
| `sandbox:node:<id>` | 判题节点运行时状态（在线 / 负载 / 心跳），由网关心跳桥接写入 | 心跳周期（过期视为离线） |
| `judge:cooldown:<user_id>:<problem_id>` | 提交冷却计数（存在即冷却中，过期视为可提交） | 冷却时长（默认配置，如 10s） |
| `judge:selftest:<user_id>:<problem_id>` | 用户自测冷却（SETNX 认领；派发失败即删） | 冷却时长（复用提交冷却配置） |
| `judge:requeue:<submission_id>` | 维护循环重派互斥锁（SETNX 防并发重复投递） | 重派窗口 |

> 缓存一致性：会话、邀请链接、判题节点状态为 Redis 唯一事实来源，不落库；榜单以数据库 `contest_rankings` 为权威数据，Redis 仅作读缓存，失效 / 封榜切换时回源数据库。全局判题并发上限由网关注册表在内存中统计（节点 in-flight 之和），不占用 Redis。

### 后台调度机制

| 机制 | 说明 | 现状 |
| --- | --- | --- |
| gRPC 网关派发 | `dispatch_submission` 按任务数最少优先选节点，`build_job_bundle` 原子认领后沿双向流推送作业；`dispatch_run_code` 同选节点策略派发用户自测并挂 pending Future 等待回传；无在线节点保持 `pending`（自测直接失败） | 已实现（随应用 lifespan 启动） |
| 网关维护循环 | 每 30s 扫描超时提交（judging 过久重置 pending 重派、断线节点 in-flight 回收） | 已实现 |
| 节点心跳桥接 | 上行 Heartbeat → 写 Redis `sandbox:node:<id>`，供管理后台沙箱状态页展示 | 已实现 |
| 比赛状态推进（`contest_transition`：封榜 / 解封 / 结束重算） | 按比赛时间周期推进 | 随 contests 模块实现 |

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
- `login_logs`、`exception_logs`：安全与异常
