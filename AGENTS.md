# PigeonOJ 项目指南

本仓库所有 AI 工具的统·一入口。`docs/` 下的文档是产品契约，代码、测试与文档保持同步。

## 必读顺序

1. `README.md` — 项目定位与快速开始
2. `docs/architecture.md` — 技术栈、分层架构、编码规范、**安全与权限**、AI 协作工作流
3. `docs/contracts.md` — 数据模型、API 契约、错误码（含跨域的所有权 / 可见性 / 编排规则）
4. `docs/operations.md` — 运行、测试、部署、Redis/调度/存储约定、判题节点部署
5. `docs/frontend.md` — 前端设计系统（改前端时必读）

## 任务 → 文档

| 任务 | 先读 |
| --- | --- |
| 改后端代码 | `architecture.md` + `contracts.md` |
| 改前端代码 | `frontend.md`（涉及 API/权限时加读 `architecture.md` + `contracts.md`） |
| 改表结构 / API / 错误码 | `contracts.md` |
| 改权限 / 越权 / 沙箱安全 | `architecture.md` §5 |
| 改配置 / 环境 / 测试 / 部署 | `operations.md` |

## 工作规则

- 优先小步变更，避免大范围重写
- 行为、API、环境变量、数据表结构或命令变更时同步更新文档（映射表见 `architecture.md` §6.3）
- 除非明确要求，不引入 `architecture.md`「明确不使用」之外的技术
- 不在代码中硬编码密钥、token、密码或环境 URL
- API 统一信封 `{ code, message, data }`，`code=0` 表示成功（见 `contracts.md` §1.1）
- 越权规则、沙箱规则、凭证规则见 `architecture.md` §5
- 代码执行仅在 isolate 沙箱进行；AI 修改代码必须用户确认后应用

## 验证

- 后端命令统一用**仓库根目录 `.venv`**：不存在就 `python -m venv .venv` 创建并装依赖，存在就直接用（激活，或免激活直接调 `.venv/Scripts/python`）；不装进全局 Python。详见 `operations.md`「后端虚拟环境」
- 后端变更：`.venv/Scripts/python src/backend/scripts/check_import_rules.py` + 最相关 pytest
- 前端变更（新工程 `src/frontend-next`）：`cd src/frontend-next && npm run lint:check && npm test && npm run build`；旧 `src/frontend` 仅作参考

## 领域约定

PigeonOJ 是 OJ 平台，判题采用「后端 gRPC 网关 + 判题节点容器内 isolate 执行」架构，后端进程不执行用户代码；首批支持 Python 3.12、C++17、Java 21；AI 能力暂缓实现。
