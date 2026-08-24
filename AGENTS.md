# Codex 项目指南

本文件是 Codex 专属的项目指南。Codex 应将 `docs/` 目录下的文档视为产品契约，保持代码、测试和文档同步。

## 必读顺序

1. `README.md` — 项目目的和快速入门
2. `docs/architecture.md` — 技术栈、分层、编码规范和安全规则
3. `docs/contracts/` — 数据模型、API 契约和错误码
4. `docs/operations.md` — 测试、部署和环境变量
5. `docs/workflow.md` — 文档同步工作流
6. 修改前端时加读 `docs/frontend.md`；重构后端模块时加读 `docs/refactoring-notes.md`

## 工作规则

- 优先小步变更，避免大范围重写
- 行为、API、环境变量、数据表结构或命令变更时，同步更新文档（见 `docs/workflow.md` 同步映射表）
- 除非任务明确要求，否则不引入新框架
- 不在代码中硬编码密钥、token、密码或环境相关 URL
- 保持示例代码可运行，或明确标注为模板示例
- API 使用统一响应信封 `{ code, message, data }`，`code=0` 表示成功（见 `docs/contracts/common.md`）
- 越权规则：所有用户数据查询必须带 `WHERE user_id = ?`；测试点期望输出、沙箱内部路径不返回前端
- 代码执行仅在 nsjail 沙箱进行；AI 修改代码必须用户确认后应用
- Codex 专属行为写在本文件或 `.codex/` 目录下

## 决策记录

在做影响架构的修改之前，先阅读 `docs/decisions/` 目录下相关的决策记录。理解已有决策的原因；若新方案与已有决策冲突，先与用户讨论。

## 验证

- 仅文档变更时，检查链接、路径和示例的一致性
- 后端变更时：`python scripts/check_import_rules.py` + 运行最相关的 pytest（见 `docs/operations.md`）
- 前端变更时，依次运行 `npm run lint:check` / `npm test` / `npm run build`
- 如果验证命令不可用，在最终回复中说明

## 领域约定

PigeonOJ 是 OJ 平台，技术栈 FastAPI / SQLAlchemy / Alembic / gRPC（判题节点网关）/ PostgreSQL / Redis / MinIO / nsjail / Vue 3。判题采用「后端 gRPC 网关 + 判题节点容器内 nsjail 执行」架构，后端进程不执行用户代码；首批支持 Python 3.12、C++17、Java 21。AI 能力（聊天 / 出题等）暂缓实现，相关契约与依赖已摘除，立项时再凭决策记录恢复。
