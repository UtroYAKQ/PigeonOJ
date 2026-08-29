# 架构与编码规范

> 技术栈、分层架构、模块结构与编码规范。安全规则见 [security.md](security.md)，运维约定见 [operations.md](operations.md)，前端契约见 [frontend.md](frontend.md)。

## 技术栈

| 类别 | 选型 | 版本 | 备注 |
| --- | --- | --- | --- |
| 后端框架 | FastAPI | - | 组织 REST 接口 |
| 数据访问 | SQLAlchemy ORM + Alembic | - | Alembic 管理迁移 |
| 判题节点网关 | gRPC（双向流） | - | 节点注册 / 心跳 / 派题 / 回传结果 |
| 数据库 | PostgreSQL | 16 | 业务实体存储 |
| 缓存 | Redis | 7 | 会话热点、邀请链接、限流、节点心跳（Key 约定见 operations.md） |
| 对象存储 | MinIO | - | 测试点、头像、图片（规范见 operations.md） |
| 代码沙箱 | nsjail | - | 进程级隔离，限制 CPU / 内存 / 时间 / 进程 / 文件系统 |
| 前端 | Vue 3 + Pinia + Naive UI + Tailwind CSS | - | Tailwind v4 辅助布局 |
| 代码编辑器 | Monaco Editor | - | |
| 部署 | Docker Compose | - | |

> gRPC 取代早期 Celery 方案；前端采用 Naive UI Nova 风格。

## 明确不使用的技术

| 技术 | 原因 |
| --- | --- |
| WebSocket / SSE 实时推送 | 榜单前端轮询刷新，不做实时推送 |
| Celery / 外部消息队列 | 判题采用进程内 asyncio gRPC 推送网关 |
| 子任务 / 分组加权计分 | 测试点分值一致，总分 = 通过测试点分值之和 |
| per-problem 语言级限制覆盖 | 题目限制以 C++ 为基准，按 sandbox_configs 全局比例换算 |
| 独立沙箱日志表 / 独立验题判题表 | 沙箱日志归 `request_logs.extra`，验题复用 `submissions` |
| 权限表（`permissions` / `role_permissions`） | 功能权限不落表，应用层按角色 code 分支判定 |
| Kubernetes / Docker Swarm | Docker Compose 编排，沙箱横向扩容 |
| NoSQL 存储业务实体 | 业务实体统一 PostgreSQL；Redis 只放短生命周期数据 |

## 分层架构

```text
api/v1（路由）→ services（业务）→ repositories（仓储）→ models → Database
                    └────────────→ core（横切：db / redis / 存储 / 异常 / 依赖注入 / 日志）
                                    rpc（判题网关基础设施：gRPC · 节点注册 · 巡检；gen/ 为生成代码）
                                    utils（纯工具：安全 · 响应 · 分页 · 校验）
                                    enums（全局枚举常量）
```

| 层 | 目录 | 职责 | 绝对不能做 |
| --- | --- | --- | --- |
| 路由层 | `app/api/v1/` | 解析 HTTP 请求，声明鉴权依赖，调用服务，返回响应信封 | ❌ 业务逻辑、SQL |
| 业务层 | `app/services/` | 业务规则、校验、编排、RBAC 分支（组合仓储完成） | ❌ 处理 HTTP 细节、手写 SQL 细节 |
| 仓储层 | `app/repositories/` | 数据访问（纯 CRUD）+ 审计日志写入助手 | ❌ 业务规则分支 |
| 判题网关基础设施 | `app/rpc/` | gRPC 网关服务、节点注册表、负载均衡派发、巡检循环（`gen/` 生成代码勿手改） | ❌ 处理 HTTP 细节 |
| 模型层 | `app/models/` | ORM 表模型（按资源域拆分，聚合包注册 metadata） | ❌ 依赖 services / repositories / rpc / api |
| 契约层 | `app/schemas/` | Pydantic 请求 / 响应模型 | ❌ 依赖 services / repositories / rpc / api |
| 枚举层 | `app/enums/` | 全局枚举常量（按业务域拆分，聚合包再导出），不 import 任何应用层 | ❌ 依赖任何应用层 |
| 核心设施 | `app/core/` | database / redis / storage / exceptions / dependency / middlewares / log / init_app | — |
| 工具层 | `app/utils/` | security / response / pagination / validation 纯函数 | ❌ 依赖 api / services / repositories / rpc / models / schemas |

### 依赖方向

永远向下且无环：

- **`app/api/` 是最上层**：任何非 api 层 import `app.api` 即违规
- **models / schemas / enums 纯净**：不依赖 services / repositories / rpc / api
- **utils 不 import** api / services / repositories / rpc / models / schemas（允许 core）
- **组合根只两处**：`app/__init__.py`（create_app 工厂）、`app/core/init_app.py`（路由注册）
- 以上由 `src/backend/scripts/check_import_rules.py` 机械检查

### 代码组织

```text
src/backend/
  run.py                      # 开发启动入口（uvicorn app:app --reload）
  backend.toml                # 后端配置（.env / 环境变量可覆盖）
  app/
    __init__.py               # create_app() 工厂（lifespan 内启动判题网关与维护循环）
    settings/config.py        # 配置加载
    api/v1/                   # 路由层（base.py + 每资源一个文件）
      base.py users.py files.py problems.py judge.py admin.py
    services/                 # 业务逻辑层：<resource>.py
      user.py file.py problem.py judge.py tag.py admin.py system_config.py
    repositories/             # 数据访问层：<resource>.py + audit 写入助手
      user.py problem.py judge.py admin.py system_config.py audit.py
    rpc/                      # 判题网关基础设施：judge_gateway.py judge_jobs.py
      gen/                      # gRPC 生成代码（勿手改）
    enums/                    # 全局枚举常量（user.py problem.py judge.py…）
    models/                   # ORM 模型（__init__.py 聚合注册全部表）
      user.py audit.py system_config.py problem.py judge.py admin.py
    schemas/                  # Pydantic 契约（user.py file.py problem.py … common.py）
    core/                     # 横切基础设施
    utils/                    # 纯工具
```

## 模块

| 模块 | 职责 | 主要实体 | 对外能力 |
| --- | --- | --- | --- |
| 认证 / 用户中心（users） | 注册登录、账号生命周期、偏好、全局角色授权、封禁 | `users`、`user_sessions`、`roles`、`user_roles` | 注册 / 登录 / 找回密码 / 会话管理 / 资料 / 角色调整 / 封禁 |
| 团队（teams） | 团队、邀请、成员、角色 | `teams`、`team_members`、`team_member_applications` | 建队 / 邀请 / 审批 / 成员管理 / 解散 |
| 题库（problems） | 题目统一管理 | `problems`、`test_cases`、`problem_tags`、`problem_verifications` | 题目 CRUD、可见性、验题、测试点管理 |
| 题单（problem-sets） | 公开 / 团队题单 | `problem_sets`、`problem_set_items` | 题单 CRUD、题目编排 |
| 比赛（contests） | 比赛、报名、榜单 | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings` | 建赛 / 报名 / 提交 / 榜单 / 封榜 |
| 判题（judge） | 提交 / 判题调度（gRPC 节点网关） | `submissions`、`submission_test_case_results`、`sandbox_configs` | 提交判题、验题提交、历史查询、节点健康 |
| 社区（community） | 通知、消息、题解、讨论、评论、举报 | `notifications`、`messages`、`solutions`、`posts`、`comments`、`reports` | 社区互动 |
| 管理 / 运维（admin） | 站点 / 认证 / 比赛 / 沙箱配置、日志查询、举报处理 | `system_configs`、`request_logs`、`login_logs`、`exception_logs`、`reports` | 配置管理、日志查询 / 导出、异常追踪、举报处理 |

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

- 枚举字段使用 `VARCHAR(n)` + CHECK 约束（SQLAlchemy 侧可用 `Enum`）；语义见对应契约文件
- 空值用 `None` 表示「无」
- 响应类型统一走泛型信封 `ApiResponse[T]` / `PaginatedResponse[T]`（`app/utils/`）：路由以 `response_model` 声明返回类型；Service 返回 Pydantic 响应模型；禁止手工拼装响应字典或在响应出口 `model_dump`（见 `docs/contracts/common.md`）
- 跨模块只 import 对方 service / repository 的公开类与函数

### 错误处理

- 错误码：`10xx` 参数 / `20xx` 认证 / `30xx` 资源 / `40xx` 频控 / `50xx` 系统（见 `docs/contracts/common.md`）+ 模块专属码
- Repository 层将数据库错误转为业务错误；Service 层不抛驱动错误
- API 响应不暴露堆栈跟踪、敏感信息

### 数据访问与迁移

- 表结构变更必须创建 Alembic 迁移（up/down）；迁移 SQL 是表结构唯一来源
- 查询显式列出所需列，不用 `SELECT *`
- 所有用户数据查询必须带 `WHERE user_id = ?`（详见 `docs/security.md` 越权规则）
