# 样例独立 JSONB 字段；验题邀请链接改存 Redis；移除代码草稿表与 AI 字段

- 日期：2026-08-24
- 状态：已采纳

## 背景

题库契约实施前复核发现四处结构性问题：

1. 展示样例与正式测试点混在 `test_cases` 一张表中，靠 `is_sample` 区分。两类数据形态本就不同——样例是「展示用字符串、永不判题」（`2026-08-15-sample-not-judged.md`），正式测试点是「MinIO 对象引用、判题专用」——同一行的两组列永远只有一组有值，展示侧还需过滤，且多组样例与正式测试点共用一套 `sort_order` 空间。
2. 验题邀请链接落在 `problem_verification_invites` 表。链接是短生命周期令牌（TTL 失效、吊销即弃），用关系表承载属于过度持久化；项目已有 Redis 承载同类数据的先例（邮箱验证码、团队邀请链接）。
3. `user_code_drafts` 用户代码草稿表无任何 API 与前端消费，属提前建表。
4. `problems.is_ai_generated` / `ai_generation_task_id` 及 AI 模块整体（聊天 / 改码 / 出题 / Token 统计）处于暂缓状态，字段与契约文档先行存在造成维护噪音。

## 决策

1. **样例拆出**：新增 `problems.samples JSONB NOT NULL DEFAULT '[]'`（数组元素 `{input, output}`，≤10 组、单项各 ≤64KB）与 `problems.samples_updated_at TIMESTAMPTZ`；`test_cases` 删除 `is_sample` / `sample_input` / `sample_output` 三列，表内只剩正式测试点（双 ossId 非空）。样例编辑走新端点 `PUT /problems/{id}/samples`（全量替换并更新 `samples_updated_at`）；`PUT /problems/{id}/test-cases` 不再接收 `is_sample`。
2. **重验判定改双条件**：`MAX(test_cases.updated_at) > verified_at` 或 `samples_updated_at > verified_at` 任一成立即须重新验题（3002 拦发布，`needs_reverification` 同口径）。原单条件只覆盖测试点，样例变更须由新列承接。
3. **验题邀请链接去表化**：删除 `problem_verification_invites` 表；发起链接邀请时写 Redis key `verify_invite:{token}` → `{"problem_id": "..."}`，TTL 即有效期；解析 / 校验读 Redis，吊销即删 key。`problem_verifications.invite_id` 列随之删除。不指定验题人：提交验题代码不限身份，存在 pending 记录时任何登录用户均可提交（`invite_token` 可选），通过后 `verifier_id` 回写实际提交人。
4. **移除用户代码草稿表**：删除 `user_code_drafts` 表、模型与契约段落；编辑器草稿需求出现时重新立项。
5. **AI 相关摘除**：删除上述两列的契约描述（从未落库）、`docs/contracts/ai.md` 及索引引用；LangGraph / LiteLLM 依赖注释与环境变量示例一并移除，待 AI 能力立项时凭决策记录恢复。

## 原因

- 样例与测试点的读写路径完全正交（展示 vs 判题），分开后详情页免子查询、全量替换测试点不再触碰样例、判题链路结构上不可能误读样例；
- 邀请链接的全部语义（生成、过期、吊销）都能用一个带 TTL 的 Redis key 表达，无需状态机列；
- 草稿表与 AI 字段均无消费方，保留即负债。

## 替代方案

- **样例留在 `test_cases` 仅加 JSONB 缓存列双写**：被否决——过渡期双写一致性成本高于一次性迁移；
- **邀请链接表保留 + 增加撤销端点**：被否决——短生命周期令牌不需要审计回溯，Redis TTL 已覆盖；
- **AI 字段先留列占位**：被否决——无消费方的列会诱发绕过契约的写入。

## 影响

- Alembic 迁移 `0008`：加两列 → 存量样例行按 `sort_order` 迁入 JSONB → 删样例行与三列；drop `user_code_drafts`、`problem_verification_invites` 表与 `problem_verifications.invite_id` 列（downgrade 均可逆，邀请历史数据不恢复）；
- 契约同步：`docs/contracts/problems.md`、`docs/contracts/index.md`（ER 图与 Redis key 清单）、`docs/architecture.md`；
- API 变化：新增 `PUT /problems/{id}/samples`；`test-cases` 入参与详情响应去掉 `is_sample` 样例字段；样例响应项不再含数据库行 id；
- 前端：写题页样例改为独立编辑区（调 samples 端点），类型定义同步。
