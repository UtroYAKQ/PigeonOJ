# 后端分包改造：模块化单体 + api.py 门面 + 平台表下沉

- 日期：2026-08-24
- 状态：**已废弃（同日被取代）**——目录组织部分由 [2026-08-24-backend-layered-restructure.md](2026-08-24-backend-layered-restructure.md)（按技术层分包）取代；「每张表的归属域」与平台表下沉思路仍在新结构中延续

## 背景

初版约定「依赖方向向下；模块间只通过 Service 通信，不得跨模块直接访问对方 Repository」，但该规则无机械检查手段，实际代码在很小的实现面上已被多处突破：

- `shared/auth/permissions.py` 反向依赖 `users.models / users.repository`
- `shared/common/config.py`、`shared/common/audit.py` 反向依赖 `admin.models / admin.repository`
- `auth/service.py` 直接使用 `users.repository`，且重复导入两处 `write_login_log`
- 题库实体（`Problem / TestCase / problem_verifications` 等）全部住在 `judge/models.py`，「题库」模块只是空壳
- 存在循环风险：`identity(users)` 需要 admin 的配置读取与日志写入，admin 又需要 users 的用户管理能力

同时确认了架构定位：本项目是**按领域分包的分层模块化单体**（Service Layer + Repository 模式），不是 DDD；规则的目标不是消灭依赖，而是让依赖**可枚举、可机械检查、保持无环**。

## 决策

### 1. 模块合并与实体归属

| 变更 | 说明 |
| --- | --- |
| `auth` 并入 `users` | 注册登录会话 + 用户中心 + 用户管理 + RBAC 判定是一个「身份与访问」上下文；包名保留 `users`（API 路径不变） |
| `problem_sets` 占位并入 `problems` | 题单可见性语义完全复用题库 owner/team/visibility 过滤（契约文件不动） |
| `Problem / ProblemTag / ProblemTagRelation / ProblemVerification / ProblemVerificationInvite / UserCodeDraft / TestCase` 迁入 `problems/models.py` | 每张表只有一个归属模块；`judge` 只拥有 `Submission / SubmissionTestCaseResult / SandboxConfig` |
| `sandbox` 不再单列 | 沙箱仅被判题链路调用（见 2026-08-18-codeforces-style-judge-architecture），语言配置归 `judge` |

### 2. 依赖方向固定为无环 DAG

```text
users ← files / problems / admin
problems ← judge
shared/infra ← 所有层
```

- 跨模块只允许 `from app.modules.<Y>.api import ...`：每个模块的 `api.py` 是**唯一出口**，其余文件（service / repository / models / deps…）视为私有
- ORM 模型可经 `api.py` 再导出供跨模块查询；验题这类跨域状态机由属主模块提供钩子函数（如 `complete_verification`），调用方不直接改对方表的行

### 3. 平台表下沉 shared/infra

`system_configs` 与三张审计日志表（`request_logs / login_logs / exception_logs`）由中间件与所有业务流程写入，是横切基础设施而非 admin 的业务资产：

- `shared/infra/system_config.py`：模型 + `ConfigRepository / ConfigService / get_category_configs`
- `shared/infra/audit.py`：模型 + 写入助手 + `LogRepository`

admin 模块只保留这些表的**管理端点**（查询 / 修改）与举报处理。由此打破 `users ↔ admin` 循环：admin → users（经 `users.api`）单向。

### 4. 机械检查

新增 `src/backend/scripts/check_import_rules.py`（AST 解析，非正则）：

1. `shared/**` 禁止 import `app.modules.*`
2. 模块 X 私有文件禁止 import 模块 Y 的非 api 文件
3. 组合根豁免：`app/main.py`、`app/worker.py`、`alembic/**`、`scripts/**`、`tests/**`

### 5. 边界取舍：验题提交端点归 judge

`POST /problems/{id}/verify`（提交验题代码）创建判题提交并派发，若放在 problems 路由会造成 problems → judge 反向边（judge 已依赖 problems）。故该端点在 `judge/routes.py` 注册，URL 不变；`GET /verify-invites/{token}` 仍属 problems。路由所在包不必与 URL 前缀一一对应。

## 替代方案

- **平台表留在 admin + 循环豁免**：改动小，但留下永久的双向依赖例外，检查脚本需要白名单，规则退化回「靠自觉」——否决
- **完整 DDD（聚合根 / 领域事件 / 充血模型）**：OJ 大部分功能是 CRUD + 权限过滤，事务脚本最省事；仅在判题状态机、比赛状态推进等不变量复杂处局部引入——暂缓，见 architecture.md 分层说明
- **引入 import-linter 第三方工具**：脚本十几行即可覆盖当前两条规则，避免新增开发依赖——否决

## 影响

- 所有跨模块导入统一为 `<module>.api`；新增模块必须提供 `api.py`（即使暂无导出）
- `alembic/env.py` 聚合导入增加 `problems.models` 与 `shared.infra.audit / system_config`
- 表结构、API 路径、错误码均不变；前端零影响
- 后续 contests / teams 接入时：contests 经 `judge.api` 创建提交与读结果，经 `problems.api` 读题目；团队角色复用 `user_roles(scope='team')` 与 users 模块判定
