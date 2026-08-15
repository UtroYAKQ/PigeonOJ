# 采用 AI-Friendly 模板的文档结构（Docs First）

- 日期：2026-08-15
- 状态：已采纳

## 背景

PigeonOJ 已有三份中文设计文档（`需求文档.md`、`数据库设计.md`、`详细设计.md`），内容完备且已交叉审定。但项目缺少 AI 协作层：无入口文件、无 README、无环境变量 / 部署示例、无决策记录，AI 无法高效读懂项目。

目标：按 [AI-Friendly-Project-Template](https://github.com/UtroYAKQ/AI-Friendly-Project-Template) 的指导重构为 AI 友好项目。

## 决策

将三份设计文档**拆解迁移**进模板的文档结构，并补齐工程文件。本次只做文档层，不生成代码骨架：

- 入口文件：`AGENTS.md`（Codex）、`.claude/CLAUDE.md`（Claude Code）——只放引用链 + 专属规则
- `README.md`：门面（定位 / 快速开始 / 技术栈 / 文档索引）
- `docs/architecture.md`：技术栈（含明确不使用）、分层、模块、编码规范、安全、RBAC 与权限矩阵、缓存与异步
- `docs/contracts/`：`common.md`（响应信封 / 错误码 / 分页）+ 按模块契约文件（数据模型 → 数据所有权 → 端点 → 错误码 → 关键流程 → 明确不做）
- `docs/operations.md`：测试 / 部署 / 环境变量
- `docs/workflow.md`：AI 读取策略、文档同步映射、输出报告格式
- `docs/decisions/`：决策记录（本文件即其一）
- 工程文件：`.gitignore`、`.env.example`、`docker/docker-compose.yml`、`docker/docker-compose-dev.yml`
- 清理：删除三份旧中文文档、空 `src/` / `script/` 目录

## 原因

- 渐进式披露：AI 按任务范围读对应文档，避免一次读全三份大文档
- 契约文件统一「数据模型 → 数据所有权 → 端点 → 错误码」结构，AI 可直接对照实现与校验
- 决策记录沉淀架构取舍，AI 不会无依据推翻已定决策
- 响应信封、错误码段、分页契约（`10xx`/`20xx`/`30xx`/`40xx`/`50xx`）从详细设计中提炼，保持既有约定

## 替代方案

- **保留三份大文档 + 加入口文件**：被否决——文档未按模块拆分，AI 定位模块成本高
- **同时生成代码骨架**：被否决（用户确认）——本轮先锁定文档契约，代码后续按契约实现

## 影响

- 三份旧中文文档内容已拆解进 `docs/`，删除后文档唯一来源为 `docs/`（表结构唯一来源仍为 Alembic 迁移 SQL）
- 后续所有代码变更须遵循 `docs/workflow.md` 的文档同步映射
- 本仓库 README 明确「当前为文档与设计阶段」，避免误以为代码已实现
