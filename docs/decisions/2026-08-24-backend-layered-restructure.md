# 后端目录重构：按技术层分包（对齐 vue-fastapi-admin）

- 日期：2026-08-24
- 状态：已实施（取代 [2026-08-24-backend-module-packaging.md](2026-08-24-backend-module-packaging.md) 的目录组织部分）；`controllers/` 已于 2026-08-25 按 [2026-08-25-backend-service-repository-split.md](2026-08-25-backend-service-repository-split.md) 拆分为 `services / repositories / rpc`，本文的分层方向与规则思路仍有效

## 背景

同日的「模块化单体」改造（见上一条决策）建立了按领域分包的结构
（`modules/<域>/{api,routes,service,repository,models,schemas}.py` + `shared/`），
并以 `check_import_rules.py` 机械约束跨模块只经 `api.py` 门面通信。

随后项目决定以后端模板仓库 vue-fastapi-admin 的结构为基准统一工程组织，
明确选择**全面照搬其按技术层分包**的目录形态，接受推翻刚定稿的门面约定。

## 决策

### 1. 目录结构（app/ 内按技术层分目录）

```text
app/
  __init__.py        # create_app() 应用工厂 + app = create_app()（组合根）
  api/v1/            # 路由层：base / users / files / problems / judge / admin
  controllers/       # 控制器：业务 Service + 数据仓储合并按资源域拆文件；audit / system_config 横切
  models/            # 全部 ORM 表模型集中（__init__.py 聚合注册 metadata）
  schemas/           # 全部 Pydantic 契约集中
  core/              # database / redis / storage / exceptions / dependency / middlewares / init_app
  utils/             # security / response / pagination / validation（纯工具）
  log/               # 日志配置
  settings/config.py # 配置加载（原 app/config.py）
  rpc_gen/           # gRPC 生成代码（原 modules/judge/rpc_gen）
run.py               # 开发启动入口（uvicorn app:app --reload）
```

- 启动锚点从 `uvicorn app.main:app` 改为 `uvicorn app:app`（Dockerfile CMD、run-local.bat、文档同步更新）
- 原 `main.py` 拆为：应用工厂（`app/__init__.py`）+ 组装件（`core/init_app.py`：lifespan / 异常注册 / 路由注册）+ 中间件（`core/middlewares.py`）+ 系统端点（`api/v1/base.py`：/health 与 /api/v1/site-config）

### 2. 合并与拆分

| 原位置 | 新位置 |
| --- | --- |
| `modules/<X>/service.py` + `repository.py` | `controllers/<x>.py`（两类共存一文件，逻辑不变） |
| `modules/users/deps.py` + `permissions.py` | `core/dependency.py` |
| `modules/judge/gateway.py` + `dispatcher.py` | `controllers/judge_gateway.py` |
| `modules/judge/jobs.py` | `controllers/judge_jobs.py` |
| `shared/infra/{database,redis,storage}.py` | `core/` 同名文件 |
| `shared/common/errors.py` | `core/exceptions.py` |
| `shared/auth/security.py` | `utils/security.py` |
| `shared/common/{response,pagination,validation}.py` | `utils/` 同名文件 |
| `shared/infra/logging.py` | `log/log.py` |
| `audit.py` / `system_config.py`（模型+服务混合） | 模型 → `models/`；服务与仓储 → `controllers/` |

### 3. 导入规则重写

`src/backend/scripts/check_import_rules.py` 改为技术分层规则：

1. `app.api/**` 仅可被 api 层内部引用（路由不可被下穿依赖）
2. `models` / `schemas` 不得 import `controllers`
3. `utils` 不 import 其他应用层
4. 豁免组合根装配件 `app/core/init_app.py` 与工具链（alembic / scripts / tests）

### 4. 领域内聚的保留

技术分层不等于放弃业务边界：控制器 / 模型 / 契约仍**按资源域拆文件**
（user / problem / judge / admin…），跨域调用直接引用对方控制器的公开类与函数；
每张表的归属域约定（contracts 文档）继续有效。

## 后果

- 正向：结构与主流 FastAPI 模板一致，新人上手成本低；模型 / 契约集中后 alembic 与测试建表只依赖 `import app.models`
- 负向（接受的代价）：跨域调用失去单一出口门面的机械约束，改为依赖 code review 维持「只调对方控制器公开成员」；原骨架占位包（teams / contests / ai / community）随目录一并移除，规划信息以 contracts 文档为准
- 中立：`finalize_verify_submission` 在重构前的 HEAD 即缺失（test_problems 2 例失败为既有问题），本次不处理
