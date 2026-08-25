# 后端分层细化：controllers 拆分为 services / repositories / rpc，新增 enums

- 日期：2026-08-25
- 状态：已实施（在 [2026-08-24-backend-layered-restructure.md](2026-08-24-backend-layered-restructure.md) 基础上细化；技术层分包的总方向不变）

## 背景

上一轮重构把后端按技术层分包后，「控制器 = Service + Repository 共存一文件」的形态在
user / problem / judge 等资源域膨胀明显：单文件同时承载业务规则、数据访问与横切写入，
职责边界模糊。本轮将控制器层按职责拆细，并顺手收敛两处历史遗留
（日志配置并入 core、gRPC 生成代码归入 rpc 包）。

## 决策

### 1. 目录结构变化

```text
app/
  api/v1/            # 路由层（不变）
  services/          # 业务逻辑层：<resource>.py = Service 类（组合仓储完成业务规则）
  repositories/      # 数据访问仓储层：<resource>.py = Repository 类（纯 CRUD）+ 审计写入助手
  rpc/               # 判题网关基础设施：judge_gateway.py / judge_jobs.py + gen/（生成代码）
  enums/             # 全局枚举常量包：按业务域拆分，__init__.py 统一再导出（消除魔法字符串）
  models/ schemas/   # 不变
  core/              # 新增 log.py（原 app/log/ 并入）；其余不变
  utils/ settings/   # 不变
```

| 原位置 | 新位置 |
| --- | --- |
| `controllers/<x>.py` 的 Service 部分 | `services/<x>.py` |
| `controllers/<x>.py` 的 Repository 部分 | `repositories/<x>.py` |
| `controllers/{judge_gateway,judge_jobs}.py` | `rpc/judge_gateway.py` / `rpc/judge_jobs.py`（网关是基础设施而非资源域服务） |
| `controllers/audit.py` 写入助手 | `repositories/audit.py`（`write_login_log` 等，签名不变） |
| `controllers/system_config.py` | 服务入 `services/system_config.py`、仓储入 `repositories/system_config.py` |
| `app/log/log.py` | `core/log.py` |
| `app/rpc_gen/` | `app/rpc/gen/`（`scripts/gen_proto.py` 产出目标同步更新；节点侧 `src/judge/node/gen` 不变） |

### 2. 导入规则重写（scripts/check_import_rules.py）

分层名更新为 `api / services / repositories / rpc / models / schemas / enums / core / utils / settings`：

1. `app.api/**` 仅可被 api 层内部引用（路由不可被下穿依赖，不变）
2. `models` / `schemas` 不得 import `services` / `repositories` / `rpc`（契约层不依赖业务逻辑）
3. `enums` 完全纯净（不 import 其他应用分层）；`utils` 不 import api / 业务三层 / models / schemas
   （允许 core / settings——validation 复用 core.exceptions 的错误定义）
4. 豁免组合根装配件 `app/core/init_app.py` 与工具链（alembic / scripts / tests），不变

### 3. 依赖方向（观察到的合法边）

```text
api → services → repositories → models → (core.database, enums)
 └→ schemas/core/utils   └→ schemas/enums     schemas → enums
rpc → services / repositories / models / enums / core（判题链路基础设施）
core → settings / utils / models / repositories（dependency 会话校验、middlewares 日志写入）
```

## 后果

- 正向：业务与数据访问分离，单文件体量下降；枚举集中后魔法字符串消除；
  判题网关的「基础设施」属性在目录名上可见；生成代码不再占据 app 顶层目录位
- 负向（接受的代价）：新增一个资源域要同步创建 api / service / repository / model / schema
  五处文件（与拆分前数量相当，仅目录不同）；跨域调用仍靠 code review 维持「只调对方公开成员」
- 中立：URL、表结构、gRPC 协议、环境变量全部不变；`finalize_verify_submission`
  缺失导致的 test_problems 2 例失败为既有问题，与本轮无关
