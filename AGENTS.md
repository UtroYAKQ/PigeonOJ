# PigeonOJ 项目指南

本仓库所有 AI 工具的统·一入口。`docs/` 下的文档是产品契约，代码、测试与文档保持同步。

## 必读顺序

1. `README.md` — 项目定位与快速开始
2. `docs/architecture.md` — 技术栈、分层架构、编码规范
3. `docs/security.md` — 安全规则、权限设计、越权约束
4. `docs/contracts/` — 数据模型、API 契约、错误码（按模块拆分）
5. `docs/operations.md` — 运行、测试、部署、Redis/调度/存储约定
6. `docs/workflow.md` — 文档同步工作流
7. `docs/frontend.md` — 前端设计系统（改前端时必读）

## 任务 → 文档

| 任务 | 先读 |
| --- | --- |
| 改后端代码 | `architecture.md` + `contracts/` |
| 改前端代码 | `frontend.md`（涉及 API/权限时加读 `architecture.md` + `contracts/`） |
| 改表结构 / API / 错误码 | `contracts/`（先读 `contracts/index.md` 定位） |
| 改配置 / 环境 / 测试 | `operations.md` |

## 工作规则

- 优先小步变更，避免大范围重写
- 行为、API、环境变量、数据表结构或命令变更时同步更新文档（映射表见 `docs/workflow.md`）
- 除非明确要求，不引入 `docs/architecture.md`「明确不使用」之外的技术
- 不在代码中硬编码密钥、token、密码或环境 URL
- API 统一信封 `{ code, message, data }`，`code=0` 表示成功（见 `docs/contracts/common.md`）
- 越权规则、沙箱规则、凭证规则见 `docs/security.md`
- 代码执行仅在 nsjail 沙箱进行；AI 修改代码必须用户确认后应用

## 验证

- 后端变更：`python src/backend/scripts/check_import_rules.py` + 最相关 pytest（见 `docs/operations.md`）
- 前端变更：`npm run lint:check` / `npm test` / `npm run build`

## 领域约定

PigeonOJ 是 OJ 平台，判题采用「后端 gRPC 网关 + 判题节点容器内 nsjail 执行」架构，后端进程不执行用户代码；首批支持 Python 3.12、C++17、Java 21；AI 能力暂缓实现。
