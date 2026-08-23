# 重构注意事项

本文档记录 PigeonOJ 后端代码重构的变更和约定，供后续开发参考。

## 一、模块依赖规则

### 1.1 shared 层隔离原则

`shared/` 层**不得依赖任何业务模块**（users、admin、judge 等）。

```
正确依赖方向：
shared → (无业务模块依赖)
users  → shared
admin  → shared, users
judge  → shared, users
auth   → shared, users, admin (受限)
files  → shared, users
```

**违规示例**：
```python
# ❌ 错误：shared 层导入 users 模块
from app.modules.users.models import User
```

**正确做法**：
```python
# ✅ 正确：业务模块导入 shared
from app.shared.common.errors import APIError
```

### 1.2 模块间依赖规则

- 模块间**禁止循环依赖**
- 高层模块可依赖低层模块，反之不可
- 横切关注点（审计、配置、权限）提取到 shared 层

---

## 二、新增共享模块

### 2.1 `shared/common/pagination.py` - 通用分页

**用途**：统一分页参数定义、查询辅助函数和响应格式。

**使用方式**：
```python
from app.shared.common.pagination import PaginationParams, PaginatedResponse, paginate

@router.get("/items")
async def list_items(pagination: PaginationParams = Depends(), db = Depends(get_db)):
    rows, total = await paginate(db, Item, [], Item.created_at, pagination)
    return ok(PaginatedResponse(items=rows, total=total, page=pagination.page, page_size=pagination.page_size))
```

### 2.2 `shared/auth/permissions.py` - 统一权限检查

**用途**：角色常量定义 + 权限检查辅助函数。

**使用方式**：
```python
from app.shared.auth.permissions import MANAGER_ROLE_CODES, is_manager, require_manager_role

# 方式1：直接检查
if await is_manager(db, user):
    ...

# 方式2：要求权限（否则抛异常）
await require_manager_role(db, user)
```

**关键常量**：
- `MANAGER_ROLE_CODES = {"admin", "tutor", "team_creator"}` - 题目管理角色集合

### 2.3 `shared/common/audit.py` - 审计日志

**用途**：登录日志、请求日志、异常日志写入（从 admin/audit.py 上提）。

**使用方式**：
```python
from app.shared.common.audit import write_login_log, write_request_log, write_exception_log
```

### 2.4 `shared/common/config.py` - 配置服务

**用途**：系统配置读取（从 admin/service.py 的 ConfigService 上提）。

**使用方式**：
```python
from app.shared.common.config import ConfigService

config = ConfigService(db)
policy = await config.get_email_code_policy()
```

**注意**：admin 模块的 `AdminConfigService` 继承自 `ConfigService`，扩展了配置管理功能。

---

## 三、认证依赖迁移

### 3.1 `users/deps.py` - 认证依赖

**用途**：当前用户 / 管理员校验（从 shared/deps.py 迁移）。

**使用方式**：
```python
from app.modules.users.deps import get_current_user, get_current_admin, parse_client_ip
```

---

## 四、ORM 序列化规范

### 4.1 Response Schema 定义

为所有面向前端的实体定义 Response Schema（`judge/schemas.py`）：

```python
class ProblemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    # ... 其他字段

class SubmissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    # ... 其他字段
```

### 4.2 使用方式

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

以下场景需要在 Routes 层显式 commit：

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
    models.py        # ORM 模型
    schemas.py       # 请求/响应 Schema
    repository.py    # 数据访问层（可选）
    service.py       # 业务逻辑层
    routes.py        # API 路由
    deps.py          # 依赖注入（可选）
```

### 6.2 空模块处理

待实现模块保留 `__init__.py` 骨架：
```python
"""模块名：功能说明。"""
```

已废弃模块的 `__init__.py` 添加迁移说明：
```python
"""模块名（兼容层，已迁移至 shared/xxx.py）。"""
```

---

## 七、重构变更清单

| 变更 | 旧位置 | 新位置 | 兼容层 |
|------|--------|--------|--------|
| 分页工具 | 各模块重复实现 | `shared/common/pagination.py` | 无需 |
| 权限检查 | `judge/service.py:53`, `files/routes.py:19` | `shared/auth/permissions.py` | 无需 |
| 审计日志 | `admin/audit.py` | `shared/common/audit.py` | 已删除 |
| 配置服务 | `admin/service.py:ConfigService` | `shared/common/config.py` | 已删除 |
| 认证依赖 | `shared/deps.py` | `users/deps.py` | 已删除 |
| ORM 序列化 | 手写 dict | `judge/schemas.py` Response Schema | 无需 |

**说明**：`shared/` 层现按职责拆分为三个子包，扁平兼容层文件已全部删除：

```
shared/
  common/    # 通用工具：errors、response、pagination、validation、config、audit
  infra/     # 基础设施：database、redis、storage、logging
  auth/      # 安全：security、permissions
```

---

## 八、后续待优化

1. **judge 模块拆分**：Problem 相关模型和服务迁移到 `problems/` 模块
2. **统一 Repository 使用**：为 Problem、Submission 创建独立 Repository
3. **分页响应统一**：所有分页接口使用 `PaginatedResponse`
4. **ORM 序列化统一**：为 admin、users 模块的实体定义 Response Schema
