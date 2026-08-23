# AI 协作工作流

> AI 处理任务的通用工作流：怎么读文档、怎么同步文档、怎么报告。文档是「唯一真相来源」，代码必须服从文档。

## 读取策略

按任务范围读，不读全部。**每次必读的基线**：`README.md` → 本文件 → 与本任务相关的 `docs/` 文件：

- 写后端代码 → `architecture.md` + `contracts/`
- **修改前端代码、样式、布局、组件、路由或用户可见文案 → 必读 `frontend.md`**；涉及 API / 权限 / 数据模型时再按范围阅读 `architecture.md` 与对应 `contracts/`
- 改表结构 / API / 错误码 → `contracts/`（先读 `contracts/index.md` 定位模块文件，再读对应模块文件）
- 改配置 / 环境 / 测试 → `operations.md`
- 做架构或选型决策前 → `docs/decisions/`（如存在）

`docs/contracts/` 按模块拆分，**先读 `index.md`**：它用「模块 → 文件」表告诉你改哪个模块、读哪个文件。

不确定时多读一个文件，不要漏约束。

## 标准工作流

1. **理解现状**：读相关文档；信息不足先向用户提问，不猜测
2. **确认**：复述理解、列出将改的文件、简述方案（如与决策记录冲突先讨论）
3. **小步实现**：每次最小有用变更；遵循 `architecture.md` 的分层与规范；前端变更同时遵循 `frontend.md` 的设计系统、响应式、可访问性与 i18n 要求
4. **验证**：按 `operations.md` 运行最相关测试；命令不可用时明确说明
5. **同步文档**：对照下方映射表更新受影响文档

## 代码变更 → 文档同步映射

| 变更类型 | 必须更新 |
| --- | --- |
| 新增/修改 API | `contracts/` 对应模块文件（端点 + 错误码） |
| 表结构 / 字段 / 索引 | `contracts/` 对应模块文件 + 创建迁移文件 |
| 新增错误码 | `contracts/common.md`（通用）或对应模块文件 |
| 新增契约文件 | `contracts/index.md`（「模块 → 文件」表新增一行） |
| 业务行为 / 验收条件 | `contracts/` 对应模块文件（端点说明） |
| 技术栈增删 | `architecture.md` + 决策记录 |
| 编码 / 分层 / 安全规范 | `architecture.md` |
| 前端设计系统、布局、组件交互、响应式、可访问性或 i18n | `frontend.md`（必要时同步 `architecture.md` 的总则） |
| 测试命令 / 策略 | `operations.md` |
| 环境变量 / 部署流程 | `operations.md` |
| 重要技术决策 | `docs/decisions/YYYY-MM-DD-xxx.md` |

## 输出报告格式（每次代码变更后必用）

```markdown
## 变更摘要
（一句话：做了什么、为什么）

## 代码变更
- `path/to/file.py` — 变更说明

## 文档同步检查
| 应检查的文档 | 状态 | 说明 |
| --- | --- | --- |
| docs/architecture.md | ✅/⬜ | … |
| docs/contracts/（含 index.md） | ✅/⬜ | … |
| docs/operations.md | ✅/⬜ | … |
| docs/decisions/ | ✅/⬜ | … |

## 验证
- 运行：`pytest` — ✅ 12 passed
- 跳过：`npm test` — 原因：本次仅改后端

## 注意事项
（需人工确认 / 已知限制 / 与决策记录冲突及处理）
```

状态：✅ 已更新 | ⬜ 无需更新 | ❌ 需要更新（说明原因）。

## 禁止事项

- ❌ 不读文档直接写代码
- ❌ 改代码行为但不更新对应文档
- ❌ 引入 `architecture.md`「明确不使用」列表中的技术
- ❌ 无决策记录推翻已有架构决策
- ❌ 谎称测试通过（没运行就说通过）
- ❌ 业务逻辑写进 Route 层；SQL 写进 Service 层之外
- ❌ API 响应暴露堆栈跟踪、测试点期望输出或敏感信息
- ❌ 用 `SELECT *` 查询；所有用户数据查询不带 `WHERE user_id = ?`
