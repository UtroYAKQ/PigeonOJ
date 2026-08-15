<p align="center">
  <img alt="Docs First" src="https://img.shields.io/badge/Docs--First-blue?style=flat-square" />
  <img alt="OJ + AI" src="https://img.shields.io/badge/OJ%20%2B%20AI-teal?style=flat-square" />
  <img alt="Platform" src="https://img.shields.io/badge/Type-Platform-purple?style=flat-square" />
</p>

<h1 align="center">PigeonOJ</h1>

<p align="center">
  <b>融合传统 Online Judge 能力与 AI 辅助能力的编程学习、训练与竞赛平台。</b><br/>
  <em>题库 · 题单 · 比赛 · 团队空间 · 沙箱判题 · AI 改码 / 编译纠错 / 出题。</em>
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
- **AI 能力**：AI 聊天辅助、AI 修改代码（用户确认后应用）、编译错误纠错、AI 生成题目。

本项目以**文档驱动**方式开发：`docs/` 下的架构、契约、运维与工作流文档是产品契约，代码、测试与文档保持同步。

## 快速开始

```bash
# 开发环境（PostgreSQL + Redis + MinIO + 后端）
docker compose -f docker/docker-compose-dev.yml up --build

# 生产环境（后端 + Celery + 前端 + 基础设施）
docker compose -f docker/docker-compose.yml up -d
```

详细命令见 [docs/operations.md](docs/operations.md)。环境变量见 [.env.example](.env.example)，本地使用 `cp .env.example .env`。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 后端 | FastAPI · SQLAlchemy · Alembic · Celery · LangGraph · LiteLLM |
| 存储 | PostgreSQL · Redis · MinIO |
| 沙箱 | nsjail（进程级隔离代码执行） |
| 前端 | Vue 3 · Pinia · Element Plus · Monaco Editor |
| 部署 | Docker Compose |

完整选型与「明确不使用的技术」见 [docs/architecture.md](docs/architecture.md)。

## 文档索引

> 按任务范围读相关文档；AI 协作工作流见 [docs/workflow.md](docs/workflow.md)。

| 文档 | 内容 | 何时读 |
| --- | --- | --- |
| [docs/architecture.md](docs/architecture.md) | 技术栈、分层、模块、编码规范、安全规则、权限矩阵 | 写代码前必读 |
| [docs/contracts/](docs/contracts/index.md) | 数据模型、API 契约、错误码（按模块拆分） | 改表结构 / API / 错误码时 |
| [docs/operations.md](docs/operations.md) | 测试、部署、环境变量 | 改配置 / 环境 / 测试时 |
| [docs/decisions/](docs/decisions/) | 架构决策记录 | 做架构或选型决策前 |

## 仓库结构

| 位置 | 内容 |
| --- | --- |
| `AGENTS.md` / `.claude/CLAUDE.md` | AI 入口文件（Codex / Claude Code 各一份） |
| `docs/architecture.md` | 技术栈、分层、编码规范、安全规则 |
| `docs/contracts/` | 数据模型、API 契约、错误码（按模块拆分） |
| `docs/operations.md` | 测试、部署、环境变量 |
| `docs/workflow.md` | AI 如何读文档、同步文档、写报告 |
| `docs/decisions/` | 架构决策记录 |
| `docker/` | Docker Compose 编排（生产 / 开发） |
| `src/backend` / `src/frontend` / `src/sandbox` | 后端 / 前端 / 沙箱服务（前后端骨架已就位，沙箱待实现） |

## 说明

- 当前阶段：文档契约已完成，前后端**基础骨架已就位**（`src/backend` + `src/frontend`，不含业务），业务功能按 `docs/contracts/` 各模块契约逐步实现。
- 沙箱执行环境首批支持 Python 3.12、C++17、Java 21。
