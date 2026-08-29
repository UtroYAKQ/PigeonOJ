﻿<p align="center">
  <img alt="Docs First" src="https://img.shields.io/badge/Docs--First-blue?style=flat-square" />
  <img alt="OJ + AI" src="https://img.shields.io/badge/OJ%20%2B%20AI-teal?style=flat-square" />
  <img alt="Platform" src="https://img.shields.io/badge/Type-Platform-purple?style=flat-square" />
</p>

<h1 align="center">PigeonOJ</h1>

<p align="center">
  <b>融合传统 Online Judge 能力与 AI 辅助能力的编程学习、训练与竞赛平台。</b><br/>
  <em>题库 · 题单 · 比赛 · 团队空间 · 沙箱判题 · AI 改码 / 编译纠错 / 出题（AI 能力规划中）。</em>
</p>

<p align="center">
  <a href="#这是什么">这是什么</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#技术栈">技术栈</a> ·
  <a href="#文档索引">文档索引</a> ·
  <a href="#仓库结构">仓库结构</a>
</p>

---

## 这是什么

PigeonOJ 是一个面向编程学习、训练和竞赛的平台：

- **传统 OJ 能力**：用户管理、题库、题单、公开/团队比赛、团队空间、代码编辑与沙箱判题。
- **AI 能力（规划中，暂缓实现）**：AI 聊天辅助、AI 修改代码（用户确认后应用）、编译错误纠错、AI 生成题目。

本项目以**文档驱动**方式开发：`docs/` 下的架构、契约、运维与工作流文档是产品契约，代码、测试与文档保持同步。

## 快速开始

- **Windows 一键启动（推荐）**：双击根目录 `run-local.bat` —— 自动拉起 PostgreSQL / MinIO / Redis，构建沙箱基础层与判题节点镜像并启动 1 个本地判题节点，执行数据库迁移与演示账号引导，随后弹出后端（8000）与前端（5173）窗口。
- **生产环境**（后端 + 前端 + 基础设施）：

  ```bash
  docker compose --env-file .env -f docker/docker-compose.yml up -d --build
  ```

- **判题节点**（默认本机 1 个；配置模板 `.env.node.example` → 复制为 `.env.node`）：

  ```bash
  docker compose --env-file .env.node --project-directory . -f docker/docker-compose-node.yml up -d --build
  ```

详细命令见 [docs/operations.md](docs/operations.md)。后端配置主文件为 [src/backend/backend.toml](src/backend/backend.toml)（`.env` / 环境变量可覆盖，模板见 [.env.example](.env.example)，本地使用 `cp .env.example .env`）。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 后端 | FastAPI · SQLAlchemy · Alembic · gRPC（判题节点网关） |
| 存储 | PostgreSQL · Redis · MinIO |
| 沙箱 | nsjail（进程级隔离代码执行） |
| 前端 | Vue 3 · Pinia · Naive UI · Tailwind CSS v4 · vue-i18n · Monaco Editor |
| 部署 | Docker Compose |

完整选型与「明确不使用的技术」见 [docs/architecture.md](docs/architecture.md)。

## 文档索引

> 按任务范围读相关文档；AI 协作工作流见 [docs/workflow.md](docs/workflow.md)。

| 文档 | 内容 | 何时读 |
| --- | --- | --- |
| [docs/architecture.md](docs/architecture.md) | 技术栈、分层架构、编码规范 | 写代码前必读 |
| [docs/security.md](docs/security.md) | 安全规则、RBAC 权限矩阵、越权约束 | 改接口 / 涉及权限时 |
| [docs/contracts/](docs/contracts/index.md) | 数据模型、API 契约、错误码（按模块拆分） | 改表结构 / API / 错误码时 |
| [docs/operations.md](docs/operations.md) | 运行、测试、部署、Redis/调度/存储约定 | 改配置 / 环境 / 测试时 |
| [docs/frontend.md](docs/frontend.md) | 前端设计系统、布局、i18n 与质量门禁 | 改前端时必读 |
## 仓库结构

| 位置 | 内容 |
| --- | --- |
| `AGENTS.md` | AI 统·一入口（必读顺序 + 任务→文档映射 + 工作规则） |
| `docs/architecture.md` | 技术栈、分层架构、编码规范 |
| `docs/security.md` | 安全规则、RBAC 权限矩阵、越权约束 |
| `docs/contracts/` | 数据模型、API 契约、错误码（按模块拆分） |
| `docs/operations.md` | 运行、测试、部署、Redis/调度/存储约定 |
| `docs/frontend.md` | 前端设计系统、布局、i18n 与质量门禁 |
| `docs/workflow.md` | AI 协作工作流与文档同步映射 |
| `docker/` | Docker Compose 编排（生产 `docker-compose.yml` 与判题节点 `docker-compose-node.yml`） |
| `src/backend` / `src/frontend` / `src/judge` | 后端 / 前端 / 判题节点（含 nsjail 沙箱镜像与节点守护进程） |

## 说明

- 当前阶段：文档契约已完成。**后端已实现 users（认证 / 用户中心 / 用户管理）/ files / problems（题库 · 测试点 · 验题记录）/ judge（提交判题调度 · 沙箱配置 · gRPC 节点网关）/ admin 模块**（含 Alembic 迁移与集成测试；模块间经 `api.py` 门面通信，规则由 `src/backend/scripts/check_import_rules.py` 检查）；**前端已实现整体布局**（左侧固定图标栏 + 顶栏面包屑/用户菜单 + 区块二级菜单）与**用户 / 管理 / 题库**页面，直连真实后端 API（题库含列表分页筛选、写题/编辑、提交判题与测试点明细；样例支持复制输入，在线试运行规划中），已建立 ESLint / Prettier / Vitest 质量门禁。判题链路为「后端 gRPC 网关 + 判题节点双向流注册/心跳负载 + 维护循环兜底重调度」架构——后端进程不执行任何用户代码，本地由 `run-local.bat` 一键拉起。其余业务功能（比赛 / 团队 / 题单 / AI / 社区等）按 `docs/contracts/` 各模块契约逐步实现（AI 模块及其模型配置 / Token 用量暂缓；团队题目可见性与验题邀请的团队侧随 teams 模块接入）。
- 沙箱执行环境首批支持 Python 3.12、C++17、Java 21。
