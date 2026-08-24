# 重构注意事项

本文档记录 PigeonOJ 后端代码重构的变更和约定，供后续开发参考。

> 当前模块分包以 `docs/decisions/2026-08-24-backend-module-packaging.md` 为准：
> auth 并入 users、题单占位并入 problems、题库实体迁入 `problems/models.py`、
> 平台表（system_configs / 审计日志）下沉 `shared/infra/`、各模块以 `api.py`
> 为唯一对外出口，并由 `scripts/check_import_rules.py` 机械检查。

## 一、模块依赖规则

### 1.1 依赖方向（无环 DAG）

```text
users ← files / problems / admin      # 跨模块一律经 users.api
problems ← judge                      # 判题读题目经 problems.api
shared/infra ← 所有层                 # shared 不依赖任何业务模块
```

- `shared/**` **不得依赖任何业务模块**；平台表模型与服务（system_configs、审计日志）属横切基础设施，放 `shared/infra/`
- 模块间只允许 `from app.modules.<Y>.api import ...`——每个模块的 `api.py` 是**唯一出口**，
  其余文件（service / repository / models / deps / permissions…）视为私有实现
- ORM 模型可经 `api.py` 再导出供跨模块查询；跨域状态变更由属主模块提供钩子函数
  （如 `complete_verification`），调用方不直接改对方表的行

**违规示例**：

```python
# ❌ 错误：直接引用对方私有文件
from app.modules.problems.service import ProblemService
# ❌ 错误：shared 层导入业务模块
from app.modules.users.models import User  # in app/shared/**
```

**正确做法**：

```python
# ✅ 正确：经对方 api.py 门面
from app.modules.problems.api import ProblemService
# ✅ 正确：业务模块导入 shared
from app.shared.common.errors import APIError
```

### 1.2 机械检查

```bash
cd src/backend && python scripts/check_import_rules.py   # AST 解析，退出码非 0 即违规
```

规则：① shared 禁止 import `app.modules.*`；② 跨模块只能 import 对方 `api.py`；
③ 组合根豁免（`app/main.py`、`alembic/**`、`scripts/**`、`tests/**`）。
新增模块必须提供 `api.py`（即使暂无导出）。

---

## 二、shared 层现状

```
shared/
  common/    # errors · response · pagination · validation
  infra/     # database · redis · storage · logging · audit（审计日志表+写入）· system_config（系统配置表+读写）
  auth/      # security（密码哈希 / token）
```

| 能力 | 位置 | 使用方式 |
| --- | --- | --- |
| 通用分页 | `shared/common/pagination.py` | `from app.shared.common.pagination import PaginationParams, PaginatedResponse, paginate` |
| 权限检查（题目管理角色） | `modules/users/permissions.py`（经 `users.api` 导出） | `from app.modules.users.api import MANAGER_ROLE_CODES, is_manager, require_manager_role` |
| 审计日志写入 | `shared/infra/audit.py` | `from app.shared.infra.audit import write_login_log, write_request_log, write_exception_log` |
| 系统配置读取 | `shared/infra/system_config.py` | `ConfigService(db).get_category_configs(...)`；admin 仅保留管理端点 |

---

## 三、认证与用户上下文

### 3.1 认证依赖（users/deps.py）

```python
from app.modules.users.api import get_current_user, get_current_admin, parse_client_ip
```

auth 包已并入 users：注册 / 登录 / 会话由 `AuthService` 承载，API 路径 `/api/v1/auth/*` 保持不变。

---

## 四、ORM 序列化规范

为所有面向前端的实体定义 Response Schema（现分属 `problems/schemas.py` 与 `judge/schemas.py`）：

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

- Service/Repository 层：使用 `flush()`（依赖 get_db 自动提交）
- Routes 层：**特定场景**需要显式 `commit()`（见 5.2）

**使用 `SessionLocal()` 的独立会话**：

- 必须显式 `commit()`（如 gateway.py、jobs.py）

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

### 6.1 标准模块结构

```
modules/
  {module}/
    __init__.py      # 模块说明
    api.py           # 对外门面（唯一出口；新增模块必须提供，即使暂无导出）
    models.py        # ORM 模型（可选；每张表只有一个归属模块）
    schemas.py       # 请求/响应 Schema
    repository.py    # 数据访问层（可选）
    service.py       # 业务逻辑层
    routes.py        # API 路由（所在包不必与 URL 前缀一一对应，见决策记录 §5）
    deps.py          # 依赖注入（可选）
```

### 6.2 空模块处理

待实现模块保留 `__init__.py` 骨架（如 teams / contests / ai / community）：

```python
"""模块名：功能说明。"""
```

---

## 七、重构变更清单

| 变更 | 旧位置 | 新位置 | 兼容层 |
|------|--------|--------|--------|
| 分页工具 | 各模块重复实现 | `shared/common/pagination.py` | 无需 |
| 权限检查 | `judge/service.py`, `files/routes.py` → `shared/auth/permissions.py` | `modules/users/permissions.py`（shared 反向依赖业务，二次迁移） | 经 `users.api` 导入 |
| 审计日志 | `admin/audit.py` → `shared/common/audit.py` | `shared/infra/audit.py`（含三张日志表模型） | 已删除 |
| 配置服务 | `admin/service.py:ConfigService` → `shared/common/config.py` | `shared/infra/system_config.py`（含 system_configs 模型） | 已删除 |
| 认证依赖 | `shared/deps.py` | `users/deps.py`（经 `users.api` 导出） | 已删除 |
| auth 模块 | `modules/auth/*` | 并入 `modules/users/`（AuthService） | 已删除，URL 不变 |
| 题库实体 | `judge/models.py` 中 Problem/TestCase 等 | `problems/models.py` | 无需 |
| problem_sets 占位包 | `modules/problem_sets/` | 并入 `problems/`（契约文件不动） | 已删除 |
| 跨模块通信 | 直接 import 对方 service/repository | 各模块 `api.py` 门面 | 机械检查 |

---

## 八、后续待优化

1. ~~judge 模块拆分：Problem 相关模型和服务迁移到 `problems/` 模块~~（已完成，见 2026-08-24 决策记录）
2. **统一 Repository 使用**：为 Problem 创建独立 Repository（Submission 已有）
3. **分页响应统一**：所有分页接口使用 `PaginatedResponse`
4. **ORM 序列化统一**：为 admin、users 模块的实体定义 Response Schema
