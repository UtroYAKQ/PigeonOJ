# 题库模块契约

> 题目统一存储（全站 / 团队）、标签、测试点、验题与代码编辑器草稿。可见性按 `team_id + visibility + status` 控制。

## 数据模型

### `problems` — 题目表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(255) | NOT NULL | 题目标题 |
| description | TEXT | NOT NULL | 题面（Markdown） |
| input_description | TEXT | NULL | 输入说明（Markdown） |
| output_description | TEXT | NULL | 输出说明（Markdown） |
| solution | TEXT | NULL | 官方题解（Markdown） |
| difficulty | VARCHAR(16) | NOT NULL DEFAULT 'easy' | `easy` / `medium` / `hard` |
| time_limit_ms | INT | NOT NULL DEFAULT 1000 | 时间限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算有效限制，见 `judge.md`「语言限制换算」） |
| memory_limit_mb | INT | NOT NULL DEFAULT 256 | 内存限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算，并受 `memory_min_mb` 下限约束） |
| spj | BOOLEAN | NOT NULL DEFAULT false | 是否启用特殊判题（SPJ） |
| spj_code | VARCHAR(512) | NULL | SPJ checker 的 MinIO ossId；限 C++，判题机内部读取，沙箱内编译一次后逐测试点运行并受资源限制 |
| team_id | UUID | NULL, FK → teams.id | 归属团队；NULL=全站题目，非 NULL=团队题目（升级公开后保留溯源） |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者 |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | 全站题目：`private` / `public`；团队题目：`admin_visible` / `team_visible` / `public`（升级后） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'draft' | `draft` 草稿 / `published` 已发布 / `archived` 已下线归档 |
| is_verified | BOOLEAN | NOT NULL DEFAULT false | 是否验题通过 |
| verified_by | UUID | NULL, FK → users.id | 验题通过审核人 |
| verified_at | TIMESTAMPTZ | NULL | 验题通过时间 |
| is_ai_generated | BOOLEAN | NOT NULL DEFAULT false | 是否由 AI 出题工具生成 |
| ai_generation_task_id | UUID | NULL, FK → ai_generation_tasks.id | 对应 AI 出题记录（与 `ai_generation_tasks.problem_id` 循环引用，分步迁移） |
| published_at | TIMESTAMPTZ | NULL | 发布 / 升级可见性时间 |
| promoted_at | TIMESTAMPTZ | NULL | 团队题目升级公开（`visibility=public`）的时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK 约束（可见性与归属匹配）：

```sql
CHECK (
  (team_id IS NULL AND visibility IN ('private','public')) OR
  (team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible','public'))
)
```

CHECK 约束（状态与验题组合）：

```sql
CHECK (status <> 'published' OR is_verified)
```

索引：INDEX(`owner_id`)、INDEX(`team_id`, `visibility`, `status`)、INDEX(`visibility`, `status`)、GIN(`title` gin_trgm_ops)

### `problem_tags` / `problem_tag_relations` — 标签

- `problem_tags`：`name` UNIQUE、`color`。主键 id，created_at。
- `problem_tag_relations`：`problem_id` / `tag_id`；UNIQUE(`problem_id`, `tag_id`)。

### `test_cases` — 测试点表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| name | VARCHAR(64) | NULL | 测试点名（如 sample1 / case1） |
| is_sample | BOOLEAN | NOT NULL DEFAULT false | 是否作为展示样例 |
| sample_input | TEXT | NULL | 样例输入（出题人字符串录入，is_sample=true 时使用） |
| sample_output | TEXT | NULL | 样例输出（字符串） |
| input_oss_id | VARCHAR(512) | NULL | 判题输入（MinIO ossId） |
| expected_output_oss_id | VARCHAR(512) | NULL | 判题期望输出（MinIO ossId） |
| score | INT | NOT NULL DEFAULT 0 | 该测试点分值 |
| sort_order | INT | NOT NULL DEFAULT 0 | 顺序 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `sort_order`)

> **样例仅用于题目详情页展示与自测，不参与正式判题**（见 `docs/decisions/2026-08-15-sample-not-judged.md`）。正式判题只使用 `input_oss_id` / `expected_output_oss_id` 指向的测试点。

### 验题表

#### `problem_verifications` — 验题记录表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| verifier_id | UUID | NULL, FK → users.id | 受邀验题人 |
| invite_id | UUID | NULL, FK → problem_verification_invites.id | 通过链接邀请时来源 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'pending' | `pending` / `passed` / `failed` |
| language | VARCHAR(32) | NULL | 验题代码语言 |
| code | TEXT | NULL | 验题提交代码（判题依据，留档） |
| comment | TEXT | NULL | 验题意见 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `status`)

#### `problem_verification_invites` — 验题邀请链接表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| token | VARCHAR(64) | NOT NULL, UNIQUE | 邀请链接令牌 |
| invited_by | UUID | NOT NULL, FK → users.id | 发起人 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | `active` / `expired` / `revoked` |
| expires_at | TIMESTAMPTZ | NULL | 有效期 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### `user_code_drafts` — 用户代码草稿表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| problem_id | UUID | NULL, FK → problems.id | 关联题目 |
| contest_id | UUID | NULL, FK → contests.id | 比赛内做题时 |
| language | VARCHAR(32) | NOT NULL | |
| code | TEXT | NOT NULL | 编辑器内容 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：PARTIAL UNIQUE(`user_id`, `problem_id`, `language`) WHERE `contest_id IS NULL`

## 数据所有权

- 题目按 `status + visibility` 双重控制访问（见下方可见性）；所有查询必须带可见性过滤
- 草稿（`status='draft'`）仅创建者本人可见
- 官方题解 `solution` 仅题目管理角色（`admin/tutor/team_creator/team_admin`）与创建者可见
- 测试点 / SPJ 文件仅题目管理角色（`admin/tutor/team_creator/team_admin`）可读写；管理角色读详情时回读测试点内容用于编辑；判题读取走服务端内部链路，不向前端暴露下载 / 预签名 URL
- 提交结果不返回测试点期望输出（`expected_output`）
- 用户代码草稿仅本人可读写（`WHERE user_id = ?`）

## 可见性设计

| 题目类型 | `team_id` | 可用 `visibility` | 题库中心可见？ | 说明 |
| --- | --- | --- | --- | --- |
| 全站题目 | NULL | `private` / `public` | 仅 `public` | `private` 仅创建者可见 |
| 团队题目 | 非空 | `admin_visible`（默认）/ `team_visible` | 否（升级前） | 团队题库内按可见性展示 |
| 团队升级公开 | 非空（保留） | `public` | 是 | 不可逆；`promoted_at` 记录时间 |

- 生命周期（`status`）与可见性（`visibility`）正交：草稿 / 发布 / 归档由 `status` 表达，私有 / 管理可见 / 团队可见 / 全站公开由 `visibility` 表达
- 题目被题单 / 比赛引用时不物理删除，下线走 `status='archived'`；引用后不自动改变题目在题库中心的可见性
- 用户在题单或比赛中访问题目时，按题单或比赛本身的访问权限展示题面

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problems | public / auth | 题库列表。默认（scope=all）题库中心仅 published+public；`scope=mine` 为管理视图（须登录）：创建者见自己全部题目，管理角色（admin/tutor/team_creator）见可管理范围全量，可叠加 `status` 过滤 | 分页/标签/难度/关键字/scope/status | problem[] |
| GET | /problems/{id} | public/owner | 题目详情（按可见性过滤） | - | problem |
| POST | /problems | admin/tutor/team_creator/team_admin | 创建题目（公开/团队） | team_id?/title/.../visibility/limits | problem |
| PUT | /problems/{id} | admin/tutor/team_creator/team_admin | 编辑题目 | ... | problem |
| PUT | /problems/{id}/test-cases | admin/tutor/team_creator/team_admin | 更新样例 / 测试点 | cases[]（input、expected_output、is_sample、score、sort_order） | - |
| POST | /problems/{id}/verify | admin/tutor/team_creator/team_admin（发起）/ 受邀验题人（凭 invite token 提交） | 发起验题 / 受邀人提交验题（双模式请求体：`code+language` 为提交，否则为发起） | verifier_id?/invite_expires_hours?/invite_token?/code?/language? | verification 或 submission_id |
| GET | /verify-invites/{token} | public | 解析验题邀请链接 | - | {problem_id, problem_title, expires_at} |
| POST | /problems/{id}/publish | admin/tutor/team_creator/team_admin | 发布（须验题通过 + 至少 1 个正式测试点） | - | problem |
| POST | /problems/{id}/archive | admin/tutor/team_creator/team_admin | 下线归档 | - | problem |
| POST | /problems/{id}/promote | admin/tutor/team_creator/team_admin | 团队题目升级公开（不可逆；teams 模块上线前返回 3002） | - | problem |
| GET | /teams/{team_id}/problems | admin/tutor/team_creator/team_admin | 团队题库列表（随 teams 模块实现） | 分页/可见性 | problem[] |
| POST | /files/upload/avatar | auth（头像） | 头像上传（multipart → ossId） | file | ossId |
| POST | /files/upload/spj | admin/tutor/team_creator | SPJ checker 源码上传（multipart → ossId，≤16MB，仅 .cpp） | file | ossId |

> 测试点不走独立上传接口：`PUT /problems/{id}/test-cases` 接收 UTF-8 的 `input` / `expected_output` 内容，每项 ≤2MB；样例写入 `sample_input` / `sample_output` 不上传 MinIO，正式测试点由后端生成对象 key 并分别上传：`problems/{problem_id}/cases/{case_id}/input` 与 `/output`，再回填 `input_oss_id` / `expected_output_oss_id`。不生成测试点归档 ZIP，前端 ZIP 只在浏览器内解压为内容。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题目不存在 |
| 2003 | 403 | 题目不可见（草稿 / 私有 / 团队题目越权） |
| 3002 | 409 | 发布未验题通过 / 升级公开不可逆重复操作 / 归档后编辑 |
| 1001 | 400 | 测试点 / SPJ 文件类型或大小不符 |
| 3003 | 409 | 重复发起验题（已有 pending 记录） |

## 当前基础前端页面

前端已提供 `/problems` 题库列表、`/problems/{id}` 题面与 Monaco 代码编辑器、提交与轮询查看 `/submissions/{id}` 评测状态，以及 `/problems/new` 写题页面。写题页面支持手工输入测试点或导入 `1.in` / `1.out` 格式 ZIP；ZIP 仅在浏览器内解压并转为可编辑内容，不向前端暴露 MinIO 对象引用。

## 关键流程 / 验收条件

1. **题目生命周期**：创建默认 `status='draft'` → 编辑 / 维护测试点 → 验题 → `publish`（`status='published'`，CHECK 强制 `is_verified`）→ `archive`（`status='archived'`）。被题单 / 比赛引用时不得物理删除，仅归档。
2. **升级公开**（仅团队题目）：`promote` 将 `visibility` 置 `public`，不可逆；`team_id` 保留溯源，`promoted_at` 记录时间。
3. **验题**：发起 `POST /problems/{id}/verify`（或生成邀请链接 → `GET /verify-invites/{token}`）→ 受邀人提交代码 → 系统按题目测试点判题（复用 `submissions`，`submit_type='verify'`）→ 全部通过 → `problem_verifications.status='passed'` 且判题链路回写 `problems.is_verified / verified_by / verified_at`。
4. **样例自测**：题目详情页展示样例字符串（`sample_input` / `sample_output`）并提供复制；在线试运行能力规划由判题节点侧专用端点承担（当前后端不执行用户代码）。

## 明确不做

- 不物理删除题目；无团队题目无「升级」概念（常规可见性变更即可）
- 不引入子任务 / 分组加权计分（见 `docs/architecture.md` 明确不使用）
- 测试点不向前端暴露下载 / 预签名 URL；提交结果不返回期望输出
- 不做 per-problem 语言级限制覆盖：题目限制为 C++ 基准，其他语言统一按 `sandbox_configs` 全局语言比例换算（见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
