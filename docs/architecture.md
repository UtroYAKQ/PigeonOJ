# 架构、规范与安全

> 技术栈、分层架构、编码规范、安全与权限设计、AI 协作工作流。
> 数据模型 / API / 错误码见 `contracts.md`，运行与部署见 `operations.md`，前端设计见 `frontend.md`。

## 目录

1. [技术栈](#1-技术栈)
2. [分层架构](#2-分层架构)
3. [模块](#3-模块)
4. [编码规范](#4-编码规范)
5. [安全与权限](#5-安全与权限)
6. [AI 协作工作流](#6-ai-协作工作流)

---

## 1. 技术栈

| 类别 | 选型 | 版本 | 备注 |
| --- | --- | --- | --- |
| 后端框架 | FastAPI | - | REST 接口 |
| 数据访问 | SQLAlchemy ORM + Alembic | - | Alembic 管理迁移（表结构唯一来源） |
| 判题节点网关 | gRPC（双向流） | - | 节点注册 / 心跳 / 派题 / 回传结果 |
| 数据库 | PostgreSQL | 16 | 业务实体存储 |
| 缓存 | Redis | 7 | 会话热点、邀请链接、限流、节点心跳（Key 见 `operations.md`） |
| 对象存储 | MinIO | - | 测试点、头像、图片 |
| 代码沙箱 | isolate（IOI 官方） | 2.1 | cgroup v2 记账 + namespace 隔离 |
| 前端 | Vue 3 + Pinia + **shadcn-vue** + Tailwind CSS v4 | - | reka-ui 无头组件（**非 Naive UI**） |
| 代码编辑器 | Monaco Editor | - | |
| 部署 | Docker Compose | - | |

### 明确不使用的技术

| 技术 | 原因 |
| --- | --- |
| WebSocket / SSE 实时推送 | 榜单前端轮询刷新 |
| Celery / 外部消息队列 | 判题采用进程内 asyncio gRPC 推送网关 |
| 子任务 / 分组加权计分 | 测试点分值一致 |
| per-problem 语言级限制覆盖 | 题目限制以 C++ 为基准，按 `sandbox_configs` 全局比例换算 |
| 独立沙箱日志表 / 独立验题判题表 | 日志归 `request_logs.extra`，验题复用 `submissions` |
| 权限表（`permissions` / `role_permissions`） | 功能权限不落表，应用层按角色 code 分支 |
| Kubernetes / Docker Swarm | Docker Compose 编排 |
| NoSQL 存储业务实体 | 业务实体统一 PostgreSQL；Redis 只放短生命周期数据 |

> 完整「明确不做」清单见 `contracts.md` §13.2。

---

## 2. 分层架构

```text
api/v1（路由）→ services（业务）→ repositories（仓储）→ models → Database
                    └────────────→ core（横切：db / redis / 存储 / 异常 / 依赖注入 / 日志）
                                    rpc（判题网关基础设施：gRPC · 节点注册 · 巡检；gen/ 为生成代码）
                                    utils（纯工具：安全 · 响应 · 分页 · 校验）
                                    enums（全局枚举常量）
```

| 层 | 目录 | 职责 | 绝对不能做 |
| --- | --- | --- | --- |
| 路由层 | `app/api/v1/` | 解析请求、声明鉴权依赖、调用服务、返回信封 | ❌ 业务逻辑、SQL |
| 业务层 | `app/services/` | 业务规则、校验、编排、RBAC 分支 | ❌ 处理 HTTP 细节、手写 SQL |
| 仓储层 | `app/repositories/` | 数据访问（纯 CRUD）+ 审计日志写入助手 | ❌ 业务规则分支 |
| 判题网关 | `app/rpc/` | gRPC 网关、节点注册表、负载均衡派发、巡检循环 | ❌ 处理 HTTP 细节 |
| 模型层 | `app/models/` | ORM 表模型（按域拆分，聚合包注册 metadata） | ❌ 依赖 services / repositories / rpc / api |
| 契约层 | `app/schemas/` | Pydantic 请求 / 响应模型 | ❌ 依赖 services / repositories / rpc / api |
| 枚举层 | `app/enums/` | 全局枚举常量 | ❌ 依赖任何应用层 |
| 核心设施 | `app/core/` | database / redis / storage / exceptions / dependency / middlewares / log / init_app / i18n | — |
| 工具层 | `app/utils/` | security / response / pagination / validation 纯函数 | ❌ 依赖 api / services / repositories / rpc / models / schemas |

### 依赖方向

永远向下且无环，由 `src/backend/scripts/check_import_rules.py` 机械检查：

- **`app/api/` 是最上层**：任何非 api 层 import `app.api` 即违规
- **models / schemas / enums 纯净**：不依赖 services / repositories / rpc / api
- **utils 不 import** api / services / repositories / rpc / models / schemas（允许 core）
- **路由层依赖一律经 `app/api/deps.py`**：认证身份（get_current_user 等）与 `XxxServiceDep` 服务 Provider 均从 deps 导入；禁止直接 import `app.services` / `app.rpc`、禁止构造 Session / Service / Repository（含 `SessionLocal` / `get_db` / `REGISTRY`）、禁止路由直接 import `app.core.dependency`。deps 是路由层唯一依赖装配点（跨上下文端口 ContestSubmitter / SubmissionDispatcher / ProblemDetailPort / TeamRolePort / UserViewPort 均在此装配）；同一请求内多个 Provider 共享请求级 db 会话（FastAPI 依赖缓存）。**事务提交归属 Service**：`get_db` 出口统一 commit，路由禁止 `commit/rollback/flush`；仅「commit 后派发判题」「commit 后失效榜单缓存」的用例在 Service 内先提交再执行后续动作
- **服务层依赖模块顶部导入**：repository / model / enum / 协作 service 一律顶部 import；函数体内局部导入仅用于**打破真实循环依赖**或生成代码条件兜底，且必须注明原因
- **组合根**：`app/__init__.py`（create_app 工厂）、`app/core/init_app.py`（路由注册）、`app/api/deps.py`（HTTP 边界唯一依赖装配点）。例外：`app/core/middlewares.py` 的独立审计会话、`tests/` 与 `scripts/`（测试与工具链可直构）
- **上下文协作用显式端口**：判题终态回写只经 `ProblemService.on_submission_finalized`（通过率计数 + 验题状态机）与 `ContestService.on_submission_finalized`（榜单）/ `full_score_for`；赛制在交题时由比赛上下文快照进提交行，judge 不回查 Contest 模型。由 `check_import_rules.py` 规则 6 守护；出现第三个订阅方时再引入领域事件总线

### 代码组织

```text
src/backend/
  run.py                      # 开发启动入口（uvicorn app:app --reload）
  backend.toml                # 后端配置（.env / 环境变量可覆盖）
  app/
    __init__.py               # create_app() 工厂（lifespan 内启动判题网关与维护循环）
    settings/config.py        # 配置加载
    api/v1/                   # 路由层（base.py + 每资源一个文件）
      base.py users.py files.py problems.py problem_sets.py contests.py
      judge.py teams.py orgs.py community.py admin.py
    services/                 # <resource>.py（含 problem_import / team_space）
    repositories/             # <resource>.py + audit 写入助手
    rpc/                      # judge_gateway.py judge_jobs.py + gen/（生成代码，勿手改）
    enums/                    # user.py problem.py judge.py contest.py team.py org.py ...
    models/                   # __init__.py 聚合注册全部表
    schemas/                  # Pydantic 契约（含 common.py）
    core/ utils/
```

---

## 3. 模块

| 模块 | 职责 | 主要实体 |
| --- | --- | --- |
| 认证 / 用户中心（users） | 注册登录、账号生命周期、偏好、全局角色、封禁 | `users`、`user_sessions`、`roles`、`user_roles` |
| 组织（orgs） | 组织、成员、组织题库（组织 = 内容所有者） | `organizations`、`org_members` |
| 团队（teams） | 团队、邀请、成员、角色（挂在组织下） | `teams`、`team_members`、`team_member_applications` |
| 题库（problems） | 题目统一管理 | `problems`、`test_cases`、`problem_tags`、`problem_verifications` |
| 题单（problem-sets） | 全站 / 团队题单 | `problem_sets`、`problem_set_items` |
| 比赛（contests） | 比赛、报名、榜单 | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings` |
| 判题（judge） | 提交 / 调度（gRPC 节点网关） | `submissions`、`submission_test_case_results`、`sandbox_configs` |
| 社区（community） | 官方题解展示、题解分享、代码广场、评论、举报 | `solutions`、`posts`、`comments`、`reports`、`code_shares` |
| 管理 / 运维（admin） | 站点 / 认证 / 比赛 / 沙箱配置、日志、举报处理 | `system_configs`、`request_logs`、`login_logs`、`exception_logs` |

> 领域关系与各模块数据模型 / 端点见 `contracts.md`。

---

## 4. 编码规范

### 命名

| 对象 | 规范 | 示例 |
| --- | --- | --- |
| 文件 / 目录 | snake_case | `problem_service.py` |
| 类 | PascalCase | `ProblemService` |
| 函数 / 变量 | snake_case | `create_problem` |
| 常量 | UPPER_SNAKE_CASE | `MAX_CODE_BYTES` |
| 数据库表 / 列 | snake_case 复数表名 | `problems`、`user_id` |
| API 路径 | kebab-case 复数名词 | `/api/v1/problem-sets` |

### Python

- 枚举字段用 `VARCHAR(n)` + CHECK 约束（SQLAlchemy 侧可用 `Enum`），语义见 `contracts.md`
- 空值用 `None` 表示「无」
- 响应类型统一走 `ApiResponse[T]` / `PaginatedResponse[T]`：路由以 `response_model` 声明；Service 返回 Pydantic 响应模型；禁止手工拼装响应字典或在出口 `model_dump`
- 跨模块只 import 对方 service / repository 的公开类与函数

### 错误处理

- 错误码分段：`10xx` 参数 / `20xx` 认证 / `30xx` 资源 / `40xx` 频控 / `50xx` 系统 + 模块专属码（见 `contracts.md` §1.2）
- Repository 层将数据库错误转为业务错误；Service 层不抛驱动错误
- 未捕获异常由 `core/exceptions.py` 兜底转信封；禁止依赖 Starlette 默认纯文本 500
- API 响应不暴露堆栈跟踪、测试点期望输出或敏感信息

### 数据访问与迁移

- 表结构变更必须创建 Alembic 迁移（up/down）；迁移 SQL 是表结构唯一来源
- 查询显式列出所需列，不用 `SELECT *`
- 所有用户数据查询必须带 `WHERE user_id = ?`

---

## 5. 安全与权限

### 5.1 角色与作用域

| 作用域 | 角色 code | 说明 |
| --- | --- | --- |
| global | `admin` | 系统管理员（全站内容兜底） |
| global | `user` | 普通用户（默认） |
| org | `org_admin` | 组织管理员 |
| org | `org_member` | 组织成员 |
| team | `team_creator` | 团队创建者 |
| team | `team_admin` | 团队管理员 |
| team | `team_member` | 团队成员 |

- 统一由 `roles`（静态种子）+ `user_roles`（运行时授权）承载；`scope` 标定全局 / 组织 / 团队，`object_id` 标定生效对象
- 功能权限不落表，中间件装载角色后按角色 `code` 在应用层分支判定
- `org_admin` ⊇ `org_member`；`team_creator` ⊇ `team_admin`（创建者额外含「分配管理员」）
- 组织 / 团队角色仅在对应资源上下文叠加判定；一个用户可加入多个组织 / 团队并持不同角色
- 一个用户的**全局角色恰好一个**（admin / user 互斥）

### 5.2 角色职责

| 角色 | 职责 |
| --- | --- |
| `admin` | 全部能力：用户管理、系统配置、运维、全站题目 / 题单 / 公开比赛、组织创建与解散 |
| `user` | 浏览题目 / 题单 / 比赛、提交（默认角色）；经组织 / 团队角色获得组织题库与团队空间能力 |
| `org_admin` | 组织成员管理（拉人 / 移出 / 授管理员）、组织信息、组织内建团队、组织题库读写 |
| `org_member` | 组织题库全量读写 |
| `team_creator` | 团队内全部管理，含「分配管理员」 |
| `team_admin` | 同 team_creator，但不含「分配管理员」 |
| `team_member` | 查看团队题单 / 比赛、提交 |

### 5.3 权限矩阵

| 功能 | user | admin | org_admin | org_member | team_creator | team_admin |
| --- | --- | --- | --- | --- | --- | --- |
| 用户中心 | 是 | 是 | 是 | 是 | 是 | 是 |
| 用户管理 | 否 | 是 | 否 | 否 | 否 | 否 |
| 创建 / 解散组织 | 否 | 是 | 否 | 否 | 否 | 否 |
| 组织成员管理 | 否 | 是 | 是（本组织） | 否 | 否 | 否 |
| 创建团队 | 否 | 是 | 是（本组织内） | 否 | 否 | 否 |
| 组织题库读 | 否 | 是 | 是 | 是 | 只读（本组织名下团队管理者） | 只读（同左） |
| 组织题库写 | 否 | 是 | 是 | 是 | 否 | 否 |
| 创建全站题 / 题单 / 公开比赛 | 否 | 是 | 否 | 否 | 否 | 否 |
| 生成团队邀请链接 | 否 | 否 | 否 | 否 | 是 | 是 |
| 分配团队管理员 | 否 | 否 | 否 | 否 | 是 | 否 |
| 管理团队题单 / 题库 / 比赛 | 否 | 否 | 否 | 否 | 是 | 是 |
| 查看公开比赛 | 是 | 是 | 是 | 是 | 是 | 是 |
| 查看所在团队比赛 | 是 | 是 | 是 | 是 | 是 | 是 |
| 系统配置 / 运维面板 | 否 | 是 | 否 | 否 | 否 | 否 |
| 使用代码编辑器 | 是 | 是 | 是 | 是 | 是 | 是 |

> 接口权限标注角色 code（逗号分隔）；`public` = 无需登录，`auth` = 登录即可，`owner` = 资源所有者本人。**前端显示不是权限校验的替代品。**
> 资源级所有权与可见性规则见 `contracts.md` §3。

### 5.4 越权规则

- 所有用户数据查询必须带 `WHERE user_id = ?`（当前登录用户）
- 团队资源查询必须带 `WHERE team_id = ?`
- 提交 `contest_id` 由服务端从请求上下文推导，不信任客户端传入
- `submit_type=verify` 须校验 `verification.verifier_id` 与当前用户一致
- 按邮箱查找用户仅限 `org_admin` / 站点 `admin`，必须**完整邮箱精确匹配**，只返回 id / email / nickname / avatar_url 等最小字段，不提供模糊用户搜索
- 返回用户对象必须排除 `password` 字段

### 5.5 沙箱安全

- 代码执行**仅在 isolate 沙箱**进行；限制 CPU / 内存 / 时间 / 进程 / 文件系统 / 网络，限制输出大小、磁盘配额、CPU 核数
- 每次调用前清空 box 可写区；作业目录只读挂 `/prog`、测试点目录只读挂 `/data`（并发作业互不可见，被判程序无法篡改源码与判定数据）；stdout / stderr 由内核 `--fsize` 封顶并按上限截断后判 OLE
- 默认禁止网络访问（禁外网 / 禁内网元数据）
- 代码和测试点由节点从内部存储准备到本地临时目录；不提供用户可控 URL 执行接口，不接受内联测试点 payload
- **后端进程不执行任何用户代码**；经 gRPC 网关派发到节点执行，后端仅承担注册认证、负载均衡、结果落库
- 节点管理页默认只绑回环（compose 映射 `127.0.0.1:18080`）；不执行用户代码、不代理任意 URL，仅 TCP 探测所填网关 host:port；注册令牌只回掩码

### 5.6 凭证与密钥

- 密码、会话 Token 哈希存储（bcrypt / argon2）
- 邮箱验证码、验题邀请链接存 Redis（短 TTL，不落库）
- 不硬编码密钥 / token / 密码 / URL；不在日志记录敏感信息
- 配置值（如 `*.password`）管理接口一律掩码返回，提交掩码值视为未修改

### 5.7 上传与文件

- 文件统一写入 MinIO；对象 key 由服务端生成（不信任客户端路径）
- 类型白名单 + 大小上限（头像 ≤2MB、测试点 ≤8MB、插图 ≤5MB、FPS 导入 ZIP ≤64MB 仅 admin）
- 图片解码预算 40MP（宽×高，头部校验先于 `img.load()`），上传与按需缩略图共用 2 路解码信号量；超限拒绝（防 5MB 压缩包构造的像素炸弹）
- 上传频控按用户 Redis 固定窗口（头像 / Logo ≤10 次/小时、公共图片 ≤30 次/小时，超次 4002）；校验失败不计配额
- 换头像时删除被替换的旧头像对象（best-effort）
- 测试点文件仅判题服务内部可读，不向前端暴露下载 / 预签名 URL

### 5.8 提交与频控

- 提交限频：user + problem 冷却（Redis）+ 全局判题并发上限；代码 ≤64KB（UTF-8 字节）
- 登录失败超次触发短时冻结（`frozen` + `frozen_until = now + 15 分钟`，到期自动恢复；冻结期拒绝一切登录），区别于管理员封禁 `banned`

### 5.9 AI 安全

- AI 修改代码必须用户确认后应用，避免自动覆盖用户代码
- AI 能力暂缓实现，相关契约与依赖已摘除

---

## 6. AI 协作工作流

> 文档是「唯一真相来源」，代码必须服从文档。

### 6.1 读取策略

按任务范围读，不读全部。必读 `AGENTS.md` → 与本任务相关的 `docs/`：

| 任务 | 先读 |
| --- | --- |
| 写后端代码 | 本文件 + `contracts.md` |
| 改前端 | `frontend.md`（涉及 API / 权限时加读本文件 + `contracts.md`） |
| 改表结构 / API / 错误码 | `contracts.md` |
| 改配置 / 环境 / 测试 / 部署 | `operations.md` |
| 涉及越权 / 安全 | 本文件 §5 |

信息不足先提问，不猜测。

### 6.2 标准工作流

1. **理解现状**：读相关文档
2. **确认**：复述理解、列出将改的文件、简述方案
3. **小步实现**：每次最小有用变更；遵循分层与前端设计系统
4. **验证**：按 `operations.md` 运行最相关测试；命令不可用时明确说明
5. **同步文档**：对照下表更新受影响文档

### 6.3 变更 → 文档同步映射

| 变更类型 | 必须更新 |
| --- | --- |
| 新增 / 修改 API | `contracts.md` 对应模块节（端点 + 错误码） |
| 表结构 / 字段 / 索引 | `contracts.md` 对应模块节 + 创建迁移 |
| 新增错误码 | `contracts.md` §1.2（通用）或模块节（专属） |
| 业务行为 / 验收条件 | `contracts.md` 对应模块节 |
| 权限角色 / 越权规则 | 本文件 §5 |
| 技术栈增删 | 本文件 §1 |
| 编码 / 分层规范 | 本文件 §2 / §4 |
| 前端设计系统、布局、组件交互、i18n | `frontend.md` |
| 测试命令 / 策略、环境变量、部署、Redis Key | `operations.md` |

### 6.4 输出报告格式

```markdown
## 变更摘要
（一句话：做了什么、为什么）

## 代码变更
- `path/to/file.py` — 变更说明

## 文档同步检查
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| docs/architecture.md | ✅/⬜/❌ | … |
| docs/contracts.md | ✅/⬜/❌ | … |
| docs/operations.md | ✅/⬜/❌ | … |
| docs/frontend.md | ✅/⬜/❌ | … |

## 验证
- 运行：`pytest` — ✅ 12 passed
- 跳过：`npm test` — 原因：本次仅改后端
```

状态：✅ 已更新 | ⬜ 无需更新 | ❌ 需要更新（说明原因）。

### 6.5 禁止事项

- ❌ 不读文档直接写代码
- ❌ 字符串硬编码（用常量声明）、魔法变量、直接用字典而不是类
- ❌ 改代码行为但不更新对应文档
- ❌ 引入 §1「明确不使用」列表中的技术
- ❌ 无充分理由推翻已有架构决策
- ❌ 谎称测试通过（没运行就说通过）
- ❌ 业务逻辑写进 Route 层；SQL 写进 Service 层之外
- ❌ API 响应暴露堆栈跟踪、测试点期望输出或敏感信息
- ❌ `SELECT *` 查询；用户数据不带 `WHERE user_id = ?`
- ❌ AI 未经用户确认自动应用代码修改
