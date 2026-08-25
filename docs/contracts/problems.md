# 题库模块契约

> 题目统一存储（全站 / 团队）、标签、测试点与验题。可见性按 `team_id + visibility + status` 控制。

## 数据模型

### `problems` — 题目表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(255) | NOT NULL | 题目标题 |
| description | TEXT | NOT NULL | 题面（Markdown） |
| input_description | TEXT | NULL | 输入说明（Markdown，**必填**：创建接口校验非空；存量列保留可空以兼容历史数据） |
| output_description | TEXT | NULL | 输出说明（Markdown，必填，同上） |
| solution | TEXT | NULL | 官方题解（Markdown） |
| samples | JSONB | NOT NULL DEFAULT '[]' | 展示样例数组（`[{"input": "...", "output": "..."}]`，出题人字符串录入；仅用于详情页展示与自测，**不参与判题**，见 `docs/decisions/2026-08-15-sample-not-judged.md`）；≤10 组，单项 input / output 各 ≤64KB |
| samples_updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 样例最近一次变更时间（重验判定依据之一） |
| time_limit_ms | INT | NOT NULL DEFAULT 1000 | 时间限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算有效限制，见 `judge.md`「语言限制换算」） |
| memory_limit_mb | INT | NOT NULL DEFAULT 256 | 内存限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算，并受 `memory_min_mb` 下限约束） |
| team_id | UUID | NULL, FK → teams.id | 归属团队；NULL=全站题目，非 NULL=团队题目（永久归属该团队，不进入公开题库） |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者 |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | 全站题目：`private` / `public`；团队题目：`admin_visible` / `team_visible` |
| status | VARCHAR(16) | NOT NULL DEFAULT 'draft' | `draft` 草稿 / `published` 已发布 / `archived` 已下线归档 |
| is_verified | BOOLEAN | NOT NULL DEFAULT false | 是否验题通过 |
| verified_by | UUID | NULL, FK → users.id | 验题通过审核人 |
| verified_at | TIMESTAMPTZ | NULL | 验题通过时间 |
| published_at | TIMESTAMPTZ | NULL | 发布时间 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

CHECK 约束（可见性与归属匹配）：

```sql
CHECK (
  (team_id IS NULL AND visibility IN ('private','public')) OR
  (team_id IS NOT NULL AND visibility IN ('admin_visible','team_visible'))
)
```

CHECK 约束（状态与验题组合）：

```sql
CHECK (status <> 'published' OR is_verified)
```

索引：INDEX(`owner_id`)、INDEX(`team_id`, `visibility`, `status`)、INDEX(`visibility`, `status`)、GIN(`title` gin_trgm_ops)

### `problem_tags` / `problem_tag_relations` — 标签

- `problem_tags`：`name` UNIQUE、`color`、`status`（`active` / `archived`，默认 `active`）。主键 id，created_at / updated_at。
- `problem_tag_relations`：`problem_id` / `tag_id`；UNIQUE(`problem_id`, `tag_id`)。
- 标签由 admin 在后台维护（新增 / 改名改色 / 归档）；**归档不删除**：题目既有关联保留并继续展示，但归档标签不再出现在激活列表，也不能被新题目选择
- 题目打标：创建 / 编辑请求体携带 `tags: string[]`（≤8 个、去重），值为**激活状态的标签名**；包含未知或已归档标签名时返回 1001

### `test_cases` — 测试点表

表内全部为**正式判题测试点**（`input_oss_id` 与 `expected_output_oss_id` 均非空）。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| name | VARCHAR(64) | NULL | 测试点名（如 case1） |
| input_oss_id | VARCHAR(512) | NOT NULL | 判题输入（MinIO 对象 key：`problems/{problem_id}/cases/{case_id}/input`） |
| expected_output_oss_id | VARCHAR(512) | NOT NULL | 判题期望输出（MinIO 对象 key） |
| sort_order | INT | NOT NULL DEFAULT 0 | 顺序 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `sort_order`)

> **展示样例不落本表**：样例以字符串数组存于 `problems.samples`，仅用于题目详情页展示与自测，不参与正式判题（见 `docs/decisions/2026-08-15-sample-not-judged.md` 与 `docs/decisions/2026-08-24-samples-jsonb-column.md`）。正式判题只使用本表测试点。

### 验题表

#### `problem_verifications` — 验题记录表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| verifier_id | UUID | NULL, FK → users.id | 验题通过时的实际提交人（判题链路回写）；发起验题时不指定验题人 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'pending' | `pending` / `passed` / `failed` |
| language | VARCHAR(32) | NULL | 验题代码语言 |
| code | TEXT | NULL | 验题提交代码（判题依据，留档） |
| comment | TEXT | NULL | 验题意见 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `status`)

#### 验题邀请链接（Redis，不建表）

- 不落库：发起链接邀请时生成 `token`，写入 Redis key `verify_invite:{token}` → value JSON `{"problem_id": "..."}`，TTL = 有效期小时数；过期自动失效
- 吊销即删除 key；解析与校验均读 Redis，无独立表结构
- 提交验题代码不限身份：存在 pending 记录时任何登录用户均可提交（`invite_token` 可选，仅用于校验链接与题目对应）；邀请链接是外部人员查看题面的入口

## 数据所有权

- 题目按 `status + visibility` 双重控制访问（见下方可见性）；所有查询必须带可见性过滤
- 题目草稿（`status='draft'`）仅创建者本人可见
- 官方题解 `solution` 仅题目管理角色（`admin/tutor/team_creator/team_admin`）与创建者可见
- 测试点文件仅题目管理角色（`admin/tutor/team_creator/team_admin`）可读写；管理角色读详情时回读测试点内容用于编辑；判题读取走服务端内部链路，不向前端暴露下载 / 预签名 URL
- 提交结果不返回测试点期望输出（`expected_output`）

## 可见性设计

| 题目类型 | `team_id` | 可用 `visibility` | 题库中心可见？ | 说明 |
| --- | --- | --- | --- | --- |
| 全站题目 | NULL | `private` / `public` | 仅 `public` | `private` 仅创建者可见 |
| 团队题目 | 非空 | `admin_visible`（默认）/ `team_visible` | 否 | 团队题库内按可见性展示；不提供进入题库中心的通道 |

- 生命周期（`status`）与可见性（`visibility`）正交：草稿 / 发布 / 归档由 `status` 表达，私有 / 管理可见 / 团队可见 / 全站公开由 `visibility` 表达
- 题目被题单 / 比赛引用时不物理删除，下线走 `status='archived'`；引用后不自动改变题目在题库中心的可见性
- 用户在题单或比赛中访问题目时，按题单或比赛本身的访问权限展示题面

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /problems | public / auth | 题库列表。默认（scope=all）题库中心仅 published+public；`scope=mine` 为管理视图（须登录）：创建者见自己全部题目，管理角色（admin/tutor/team_creator）见可管理范围全量，可叠加 `status` 过滤；mine 视图每项附 `needs_reverification`（未验题或测试点/样例晚于最近验题通过时间变更） | 分页/标签/关键字/scope/status | problem[] |
| GET | /problems/tags | public | 激活标签列表（打标选择器与列表筛选用，仅 `status='active'`） | - | tag[]（id/name/color） |
| GET | /admin/tags | admin | 标签管理全量列表（含已归档） | - | tag[] |
| POST | /admin/tags | admin | 新增标签（name 唯一，重复返回 1001） | name/color? | tag |
| PUT | /admin/tags/{id} | admin | 修改标签名称 / 颜色 | name?/color? | tag |
| POST | /admin/tags/{id}/archive | admin | 归档标签（关联保留、不再可选） | - | tag |
| GET | /problems/{id} | public/owner | 题目详情（按可见性过滤） | - | problem |
| POST | /problems | admin/tutor/team_creator/team_admin | 创建题目（公开/团队） | team_id?/title/.../tags?/visibility/limits | problem |
| PUT | /problems/{id} | admin/tutor/team_creator/team_admin | 编辑题目 | ...（`tags` 全量替换标签关联） | problem |
| PUT | /problems/{id}/test-cases | admin/tutor/team_creator/team_admin | 全量替换正式测试点（出题不设分值；提交得分由判题服务端按通过比例派生，比赛计分随 contests 模块配置）；被替换测试点的 MinIO 旧对象异步清理 | cases[]（name?、input、expected_output、sort_order） | - |
| PATCH | /problems/{id}/test-cases | admin/tutor/team_creator/team_admin | 增量更新正式测试点（前端编辑器按行 diff 只提交变化的行）：upserts 带 id 为修改（input/expected_output 留空 = 内容不变，可仅改名 / 调序；未触碰行不更新 `updated_at`，不触发「需重新验题」与判题节点 data_version 缓存失效）、无 id 为新增（输入输出不能全空）；delete_ids 删除指定测试点（历史判题结果保留，`test_case_id` 由 ON DELETE SET NULL 置空）；同一 id 不得同时出现在 upserts 与 delete_ids（1001），未知 id 返回 3001；被替换内容的 MinIO 旧对象异步清理 | upserts[]（id?、name?、input?、expected_output?、sort_order?）/ delete_ids[] | cases[]（服务器权威全量列表，含内容与 id，供前端重置基线） |
| PUT | /problems/{id}/samples | admin/tutor/team_creator/team_admin | 全量替换展示样例（写 `problems.samples`，同时更新 `samples_updated_at`；不上传 MinIO） | samples[]（input、output），≤10 组、单项各 ≤64KB | - |
| POST | /problems/{id}/verify | admin/tutor/team_creator/team_admin（发起）/ auth（提交验题代码） | 发起验题 / 提交验题代码（双模式请求体：`code+language` 为提交，否则为发起）；提交不限身份，`invite_token` 可选 | invite_expires_hours?/invite_token?/code?/language? | verification 或 submission_id |
| GET | /verify-invites/{token} | public | 解析验题邀请链接（数据源 Redis `verify_invite:{token}`；返回题面与样例供受邀人查看，不含正式测试点内容与题解；`expires_at` 由 TTL 推算） | - | {problem_id, problem_title, expires_at, description, input_description?, output_description?, tags[], time_limit_ms, memory_limit_mb, samples[]} |
| POST | /problems/{id}/publish | admin/tutor/team_creator/team_admin | 发布（须验题通过 + 至少 1 个正式测试点；测试点 / 样例更新时间晚于 verified_at 时返回 3002，须重新验题） | - | problem |
| POST | /problems/{id}/archive | admin/tutor/team_creator/team_admin | 下线归档 | - | problem |
| GET | /teams/{team_id}/problems | admin/tutor/team_creator/team_admin | 团队题库列表（随 teams 模块实现） | 分页/可见性 | problem[] |
| POST | /files/upload/avatar | auth（头像） | 头像上传（multipart → ossId） | file | ossId |

> 测试点与样例均不走独立上传接口：`PUT /problems/{id}/test-cases` 接收 UTF-8 的 `input` / `expected_output` 内容（每项 ≤2MB），全部作为正式测试点由后端生成对象 key 并分别上传 `problems/{problem_id}/cases/{case_id}/input` 与 `/output`，回填双 ossId；样例经 `PUT /problems/{id}/samples` 直接存库（≤10 组、单项各 ≤64KB），不上传 MinIO。不生成测试点归档 ZIP，前端 ZIP 只在浏览器内解压为内容。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题目不存在 |
| 2003 | 403 | 题目不可见（草稿 / 私有 / 团队题目越权） |
| 3002 | 409 | 发布未验题通过 / 归档后编辑 |
| 1001 | 400 | 测试点文件类型或大小不符 |
| 3003 | 409 | 重复发起验题（已有 pending 记录） |

## 当前基础前端页面

前端已提供 `/problems` 题库列表（常驻分页：总数 + 页容量切换；搜索防抖兼容中文输入法）、`/problems/{id}` 题目详情、提交与轮询查看 `/submissions/{id}` 评测状态，以及 `/problems/new` 写题页面。详情页为「题面 + 编辑器」可拖拽双栏布局：桌面端左右两栏独立滚动、分隔条可拖拽调宽（比例持久化，双击复位），窄屏（<900px）自动上下堆叠；题面 / 输入输出说明 / 官方题解按 Markdown 渲染（markdown-it + DOMPurify，见 `docs/decisions/2026-08-23-problem-statement-markdown.md`），样例仍为等宽文本块并提供复制。编辑器语言切换不覆盖已写代码；提交判题前需经确认框二次确认。评测结果页轮询 2s 一次、上限约 5 分钟后停止自动刷新并提示手动刷新。写题页面支持手工输入测试点或导入 `1.in` / `1.out` 格式 ZIP；ZIP 仅在浏览器内解压并转为可编辑内容，不向前端暴露 MinIO 对象引用。

## 关键流程 / 验收条件

1. **题目生命周期**：创建默认 `status='draft'` → 编辑 / 维护测试点 → 验题 → `publish`（`status='published'`，CHECK 强制 `is_verified`）→ `archive`（`status='archived'`）。被题单 / 比赛引用时不得物理删除，仅归档。
2. **验题时效**：题目内容（题面等）变更不影响验题有效性；**测试点或样例在最近一次验题通过后发生变更，则须重新走验题流程才能发布**——判定依据为 `MAX(test_cases.updated_at) > problems.verified_at` **或** `problems.samples_updated_at > problems.verified_at`，发布接口违反时返回 3002；`scope=mine` 列表与详情分别以 `needs_reverification` 字段透出。
3. **验题**：发起 `POST /problems/{id}/verify`（生成邀请链接存 Redis，或不带参数创建空白记录）→ 任意登录用户提交代码（凭邀请链接或直接提交，身份不限）→ 系统按题目正式测试点判题（复用 `submissions`，`submit_type='verify'`）→ 全部通过 → `problem_verifications.status='passed'` 且判题链路回写 `problems.is_verified / verified_by / verified_at`（`verifier_id` 回写实际提交人）。
4. **样例自测**：题目详情页展示样例字符串（`problems.samples` 数组）并提供复制；在线试运行能力规划由判题节点侧专用端点承担（当前后端不执行用户代码）。

## 明确不做

- 不物理删除题目；团队题目不设「升级公开」通道——公开题库仅来自全站题目（工作区 / admin 直出），团队是封闭空间
- 不支持 SPJ 特判：判题仅标准比对（忽略行尾空白与末尾换行、行内严格），无 checker 机制
- 不引入子任务 / 分组加权计分（见 `docs/architecture.md` 明确不使用）
- 测试点不向前端暴露下载 / 预签名 URL；提交结果不返回期望输出
- 不建验题邀请链接表（Redis 承载）与用户代码草稿表；AI 出题相关字段（`is_ai_generated` / `ai_generation_task_id`）随 AI 能力迭代再引入，当前不落库
- 不做 per-problem 语言级限制覆盖：题目限制为 C++ 基准，其他语言统一按 `sandbox_configs` 全局语言比例换算（见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
