# 重构注意事项

本文档记录 PigeonOJ 后端代码重构的变更和约定，供后续开发参考。

> 当前目录结构以 `docs/decisions/2026-08-24-backend-layered-restructure.md` 为准：
> 后端按**技术层分包**（对齐 vue-fastapi-admin 模板）——`api/v1` 路由层、
> `controllers` 控制器（业务 + 仓储）、`models` / `schemas` 契约集中、
> `core` 核心设施、`utils` 纯工具；应用入口为 `app/__init__.py` 的 `create_app()`
> 工厂，由根级 `run.py` 启动。分层规则由 `scripts/check_import_rules.py` 机械检查。
> 业务域仍按资源域拆分文件（user / problem / judge / admin…），
> 「每张表的归属域」约定见 `docs/contracts/` 各模块契约。

## 一、分层依赖规则

### 1.1 依赖方向（无环 DAG）

```text
api/v1 → controllers → models → Database
           └→ core / utils      # core：database/redis/storage/exceptions/dependency
utils 保持纯净                   # 不 import api/controllers/models/schemas
models / schemas 不依赖 controllers
```

- **`app/api/**` 是最上层**：任何非 api 层 import `app.api` 即违规
- 组合根只有两处允许装配全图：`app/__init__.py`（工厂）与 `core/init_app.py`（路由注册，机械检查豁免）
- 认证依赖在 `core/dependency.py`（允许引用 `controllers/user.py` 的仓储做会话校验）
- 跨资源域调用直接引用对方控制器的公开类与函数
  （如 judge 引用 `controllers/problem.py` 的 `get_problem / can_manage_problem` 钩子）

**违规示例**：

```python
# ❌ 错误：controllers 里 import 路由层
from app.api.v1.problems import router          # in app/controllers/**
# ❌ 错误：模型层依赖业务逻辑
from app.controllers.problem import get_problem  # in app/models/**
```

**正确做法**：

```python
# ✅ 正确：路由层引用控制器与契约
from app.controllers.problem import ProblemService
from app.schemas.problem import ProblemCreate
# ✅ 正确：控制器引用核心设施
from app.core.exceptions import APIError
```

### 1.2 机械检查

```bash
cd src/backend && python scripts/check_import_rules.py   # AST 解析，退出码非 0 即违规
```

规则：① api 层不被任何其他层 import；② models/schemas 禁止依赖 controllers；
③ utils 纯净；④ 组合根装配件豁免（`app/core/init_app.py`、`alembic/**`、`scripts/**`、`tests/**`）。

---

## 二、横切能力现状

| 能力 | 位置 | 使用方式 |
| --- | --- | --- |
| 通用分页 | `utils/pagination.py` | `from app.utils.pagination import PaginationParams, PaginatedResponse, paginate` |
| 权限检查（题目管理角色） | `core/dependency.py` | `from app.core.dependency import MANAGER_ROLE_CODES, is_manager, require_manager_role` |
| 审计日志写入 | `controllers/audit.py`（表模型在 `models/audit.py`） | `from app.controllers.audit import write_login_log, write_request_log, write_exception_log` |
| 系统配置读取 | `controllers/system_config.py`（表模型在 `models/system_config.py`） | `ConfigService(db).get_value(...)`；admin 仅保留管理端点 |

---

## 三、认证与用户上下文

### 3.1 认证依赖

```python
from app.core.dependency import get_current_user, get_current_admin, parse_client_ip
```

注册 / 登录 / 会话业务在 `controllers/user.py` 的 `AuthService`，API 路径 `/api/v1/auth/*`。

---

## 四、ORM 序列化规范

为所有面向前端的实体定义 Response Schema（现分属 `schemas/problem.py` 与 `schemas/judge.py`）：

```python
class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    # ... 其他字段
```

```python
# ✅ 正确：使用 Pydantic model_validate
problem_dict = ProblemSummary.model_validate(problem).model_dump(mode="json")

# ❌ 错误：手写 dict 组装
problem_dict = {"id": str(problem.id), "title": problem.title, ...}
```

---

## 五、事务管理规范

### 5.1 commit/flush 规则

**使用 `get_db` 依赖的路由**：

- Controller 层：使用 `flush()`（依赖 get_db 自动提交）
- Routes 层：**特定场景**需要显式 `commit()`（见 5.2）

**使用 `SessionLocal()` 的独立会话**：

- 必须显式 `commit()`（如 judge_gateway.py、judge_jobs.py）

### 5.2 Routes 层显式 commit 场景

```python
# 场景1：dispatch_submission 需要读取已提交的数据
submission = await Service(db).create(user, body)
await db.commit()  # 确保 submission 已持久化
await dispatch_submission(submission.id)

# 场景2：需要返回刚创建的数据给前端
problem = await Service(db).create(user, body)
await db.commit()  # 确保 problem.id 已生成
return ok(_summary(problem))
```

**其他场景**：不显式 commit，依赖 get_db 自动提交。

---

## 六、文件组织约定

### 6.1 技术分层结构

```
app/
  __init__.py        # create_app() 工厂（组合根）
  api/v1/            # {resource}.py 路由 + base.py（/health、/site-config）
  controllers/       # {resource}.py = Service + Repository；audit / system_config 横切
  models/            # {resource}.py ORM 模型；__init__.py 聚合注册 metadata
  schemas/           # {resource}.py Pydantic 契约
  core/              # database · redis · storage · exceptions · dependency · middlewares · init_app
  utils/             # security · response · pagination · validation
  log/log.py         # 日志配置
  settings/config.py # 配置加载
  rpc_gen/           # gRPC 生成代码（scripts/gen_proto.py 产出，勿手改）
run.py               # 开发启动（uvicorn app:app --reload）
```

新增资源域时同步创建 `api/v1/<x>.py`、`controllers/<x>.py`、`models/<x>.py`
（并加入 `models/__init__.py` 聚合）、`schemas/<x>.py`。

---

## 七、重构变更清单

| 变更 | 旧位置 | 新位置 | 兼容层 |
|------|--------|--------|--------|
| 应用工厂 | `app/main.py` | `app/__init__.py` + `core/init_app.py` + `core/middlewares.py` + `api/v1/base.py` | 启动锚点改为 `uvicorn app:app` |
| 配置 | `app/config.py` | `settings/config.py` | 无需 |
| 业务+仓储 | `modules/<X>/{service,repository}.py` | `controllers/<x>.py` | 无需 |
| 路由 | `modules/<X>/routes.py` | `api/v1/<x>.py` | URL 全部不变 |
| ORM 模型 | `modules/<X>/models.py` | `models/<x>.py`（聚合包） | alembic / 测试经 `import app.models` |
| 契约 | `modules/<X>/schemas.py` | `schemas/<x>.py` | 无需 |
| 认证依赖 | `users/{deps,permissions}.py` | `core/dependency.py` | 无需 |
| 判题网关 | `judge/{gateway,dispatcher,jobs}.py` | `controllers/judge_{gateway,jobs}.py` | gRPC 端口不变 |
| 核心设施 | `shared/infra/{database,redis,storage}.py` | `core/` 同名文件 | 无需 |
| 错误类 | `shared/common/errors.py` | `core/exceptions.py` | 无需 |
| 工具 | `shared/auth/security.py`、`shared/common/*` | `utils/*` | 无需 |
| 日志配置 | `shared/infra/logging.py` | `log/log.py` | 无需 |
| 平台表 | `shared/infra/{audit,system_config}.py`（混合） | 模型入 `models/`、服务入 `controllers/` | 无需 |
| gRPC stub | `modules/judge/rpc_gen` | `app/rpc_gen` | gen_proto.py 同步更新 |
| 骨架占位包 | `modules/{teams,contests,ai,community}` | 移除（规划见 contracts 文档） | 已删除 |

---

## 八、后续待优化

1. **统一 Repository 使用**：为 Problem 创建独立 Repository 类（当前查询散在控制器函数中）
2. **分页响应统一**：所有分页接口使用 `PaginatedResponse`
3. **ORM 序列化统一**：为 admin、users 资源域的实体定义 Response Schema
4. **既有测试失败修复**：`finalize_verify_submission` 在重构前即缺失
   （test_problems 2 例失败，与本轮重构无关）
