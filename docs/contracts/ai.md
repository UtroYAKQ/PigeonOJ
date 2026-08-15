# AI 模块契约

> AI 聊天、改码、编译纠错、出题、Token 用量与模型配置。AI 编排用 LangGraph，模型调用统一经 LiteLLM。

## 数据模型

### `ai_conversations` — AI 聊天会话表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| context_type | VARCHAR(32) | NOT NULL | `editor` / `problem` / `compile_fix` / `general` |
| problem_id | UUID | NULL, FK → problems.id | 编辑器 / 题目上下文 |
| title | VARCHAR(128) | NULL | 会话标题 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `updated_at DESC`)

### `ai_messages` — AI 会话消息表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| conversation_id | UUID | NOT NULL, FK → ai_conversations.id | |
| role | VARCHAR(16) | NOT NULL | `user` / `assistant` / `system` / `tool` |
| content | TEXT | NULL | 文本内容 |
| tool_name | VARCHAR(64) | NULL | 调用的工具（改代码 / 编译纠错） |
| tool_result | JSONB | NULL | 工具返回（含 AI 建议代码 / diff，供用户确认后应用） |
| model | VARCHAR(128) | NULL | 使用的模型 |
| token_usage | JSONB | NULL | `{prompt_tokens, completion_tokens}` |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`conversation_id`, `created_at`)

> AI 修改代码的「待确认」状态不单独建表：建议修改（diff / 全文）保存在 `tool_result`，前端在用户确认后才应用到编辑器，符合「AI 不能直接覆盖代码」安全要求。

### `ai_requests` — AI 请求表

统一承载 AI 调用记录与 Token 用量统计。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| request_id | VARCHAR(64) | NOT NULL, UNIQUE | 请求追踪 ID |
| user_id | UUID | NOT NULL, FK → users.id | 请求用户 |
| conversation_id | UUID | NULL, FK → ai_conversations.id | 所属会话 |
| model | VARCHAR(128) | NOT NULL | 使用的模型 |
| purpose | VARCHAR(32) | NOT NULL | `chat` / `modify_code` / `compile_fix` / `generate_problem` |
| prompt_tokens | INT | NOT NULL DEFAULT 0 | |
| completion_tokens | INT | NOT NULL DEFAULT 0 | |
| total_tokens | INT | NOT NULL DEFAULT 0 | |
| duration_ms | INT | NULL | 调用耗时 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'success' | `success` / `error` |
| error | TEXT | NULL | 失败原因 |
| request_summary | JSONB | NULL | 请求摘要（脱敏） |
| response_summary | JSONB | NULL | 响应摘要（脱敏） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `created_at`)、INDEX(`purpose`, `created_at`)、INDEX(`status`, `created_at`)

### `user_token_stats` — 用户 Token 统计表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| stat_date | DATE | NOT NULL | 统计日期（按天） |
| model | VARCHAR(128) | NOT NULL | |
| purpose | VARCHAR(32) | NOT NULL | `chat` / `modify_code` / `compile_fix` / `generate_problem` |
| prompt_tokens | BIGINT | NOT NULL DEFAULT 0 | 累计输入 token |
| completion_tokens | BIGINT | NOT NULL DEFAULT 0 | 累计输出 token |
| total_tokens | BIGINT | NOT NULL DEFAULT 0 | 累计总 token |
| request_count | INT | NOT NULL DEFAULT 0 | 累计请求次数 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：UNIQUE(`user_id`, `stat_date`, `model`, `purpose`)、INDEX(`user_id`, `stat_date`)

> 数据来源为 `ai_requests`：每次请求写入时增量 upsert，或由 Celery 定时任务 `aggregate_token_stats` 按天汇总。当前版本仅统计、不做额度控制。

### `ai_generation_tasks` — AI 出题任务表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 出题人 |
| team_id | UUID | NULL, FK → teams.id | 归属团队（团队管理员出题时必填） |
| prompt | TEXT | NULL | 出题提示词 |
| config | JSONB | NULL | 出题配置（标签 / 难度 / 数量等） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'running' | `running` / `succeeded` / `failed` |
| model | VARCHAR(128) | NULL | |
| result | JSONB | NULL | 生成内容：题面 / 样例 / 测试点 / 题解 / 标签 / 难度 / 时空限制 |
| problem_id | UUID | NULL, FK → problems.id | 落库后的题目草稿 |
| token_usage | JSONB | NULL | |
| error | TEXT | NULL | 失败原因 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `status`)

> 循环引用处理：本表 `problem_id` 与 `problems.ai_generation_task_id` 相互外键构成循环依赖。Alembic 迁移分两步：① 建两表时只建一侧外键（保留 `problems.ai_generation_task_id`）；② 数据初始化后 `ALTER TABLE ai_generation_tasks ADD CONSTRAINT ... FOREIGN KEY (problem_id) REFERENCES problems(id)` 补齐另一侧。

### `model_configs` — 大模型配置表

通过 LiteLLM 接入不同模型提供方，为各 AI 能力提供模型。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| name | VARCHAR(128) | NOT NULL | 配置名（展示用） |
| provider | VARCHAR(64) | NOT NULL | LiteLLM provider 标识 |
| model_name | VARCHAR(128) | NOT NULL | 模型名 |
| api_base | VARCHAR(512) | NULL | 服务地址 |
| api_key | VARCHAR(512) | NULL | API Key（加密存储） |
| purpose | VARCHAR(32) | NOT NULL | `chat` / `modify_code` / `compile_fix` / `generate_problem` |
| extra_params | JSONB | NULL | 温度 / 超时 / 重试 / 最大 token 等 |
| is_enabled | BOOLEAN | NOT NULL DEFAULT true | |
| priority | INT | NOT NULL DEFAULT 0 | 同一 purpose 下生效优先级，越小越优先 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`purpose`, `is_enabled`, `priority`)

> 同一 purpose 可有多个模型配置：`is_enabled` 标记是否启用，`priority` 决定选中顺序（取启用且 priority 最小者）。

## 数据所有权

- AI 会话、消息、请求、Token 统计、出题任务均按用户隔离：所有 SQL 必须带 `WHERE user_id = ?`
- AI 出题任务仅发起人可查询结果（`owner`）
- 模型配置（含 API Key）仅系统管理员可读写（见 `admin.md`）；Key 加密存储，不随接口返回明文
- AI 修改代码必须用户确认后应用；AI 建议保存在 `tool_result`，前端确认后才写入 `user_code_drafts`

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /ai/chat | auth | AI 聊天 | conversation_id?, content, problem_id? | message |
| POST | /ai/modify-code | auth | AI 修改代码 | code, problem_id?, instruction | suggestion(diff) |
| POST | /ai/apply-modification | auth | 确认应用修改 | message_id, code | - |
| POST | /ai/compile-fix | auth | 编译纠错 | code, language, compile_error? | suggestion |
| POST | /ai/generate-problem | admin/tutor/team_creator/team_admin | AI 出题 | prompt, config, team_id? | task_id |
| GET | /ai/generate-problems/{task_id} | owner | AI 出题任务状态 / 结果查询 | - | task{status, problem_id?, error?} |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 会话 / 出题任务不存在 |
| 2003 | 403 | 越权访问他人会话 / 任务 |
| 5001 | 502 | 上游大模型调用失败 |
| 4002 | 429 | AI 调用限流 |

## 关键流程 / 验收条件

1. **AI 修改代码（用户确认）**：用户触发 → 调用大模型生成修改方案（diff / 全文）→ AI 建议存入 `ai_messages.tool_result` → 前端展示 diff 等待确认 → 用户批准 → 应用到编辑器 + 更新 `user_code_drafts`；用户拒绝 → 丢弃不落库。AI 生成内容绝不直接覆盖代码，确认在客户端完成，服务端不设独立审批表。
2. **AI 出题**：用户配置提示词 / 参数 → 创建 `ai_generation_tasks(running)` → Celery 执行：调用模型生成 题面 / 样例 / 测试点 / 题解 / 标签 / 难度 / 限制 → 生成样例后调用 `POST /sandbox/sample-run` 自校验样例正确性 → 落库为 `problems` 草稿（`is_ai_generated=true`）→ 任务标记 `succeeded`、记录 token 用量。AI 生成题目不自动进入公开 / 团队题库，仍须出题人完善并验题后发布。归属：团队管理员出题时任务携带 `team_id`，落库题目草稿归属该团队；导师 / 系统管理员全站出题（`team_id` 为空）生成全站题目草稿。
3. **编译纠错**：用户提交编译错误 → 调模型分析并给出修复建议或修改方案；必要时内部调用样例执行接口自测。
4. **Token 统计**：每次 AI 调用写 `ai_requests`；按天汇总（增量 upsert 或定时任务）至 `user_token_stats`，供 `admin` 在用户管理查看「用户 AI Token 使用情况」。

## 明确不做

- 当前版本不做 Token 额度控制（仅统计）
- AI 生成的题目不自动发布；不自动进入公开 / 团队题库
- AI 修改代码不自动覆盖（必须用户确认）
- 模型 API Key 不在接口中返回明文（加密存储，仅 `admin` 管理）
