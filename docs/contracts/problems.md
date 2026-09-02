# 题库模块契约

> 题目统一存储（全站 / 团队）、标签、测试点与验题。可见性按 `team_id + visibility + status` 控制。

## 数据模型

### `problems` — 题目表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| title | VARCHAR(255) | NOT NULL | 题目标题 |
| background | TEXT | NOT NULL DEFAULT '无' | 题目背景（Markdown，**必填**：创建接口校验非空；存量行由迁移回填为「无」；详情页渲染于题面之前） |
| description | TEXT | NOT NULL | 题面（Markdown） |
| input_description | TEXT | NULL | 输入说明（Markdown，**必填**：创建接口校验非空；存量列保留可空以兼容历史数据） |
| output_description | TEXT | NULL | 输出说明（Markdown，必填，同上） |
| note | TEXT | NULL | 题面说明（Markdown，**可选**：NULL=未填写；详情页渲染于题面最后；PUT 编辑传空字符串 = 清空） |
| solution | TEXT | NULL | 官方题解（Markdown） |
| samples | JSONB | NOT NULL DEFAULT '[]' | 展示样例数组（`[{"input": "...", "output": "...", "explanation": "..."}]`，出题人字符串录入；`explanation` 选填 Markdown 样例解释，缺省/空 = 该组无解释；仅用于详情页展示与自测，**不参与判题**）；≤10 组，input / output 各 ≤64KB、explanation ≤64KB |
| samples_updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 样例最近一次变更时间（重验判定依据之一） |
| active_case_ids | JSONB | NOT NULL DEFAULT '[]' | 生效测试点 id 列表（test_cases.id 引用；判题唯一数据来源） |
| pending_case_ids | JSONB | NULL DEFAULT NULL | 暂存测试点 id 列表（编辑目标状态，验题判定对象）；**NULL = 无暂存改动**，数组（含 `'[]'`）= 有暂存改动 |
| case_status | VARCHAR(16) | NOT NULL | 测试点集合状态缓存：`empty` / `to_verify` / `to_reverify` / `verified`（已验待生效） / `ok`，与两列表及 `pending_verified` 同事务维护；生效集非空后永不为空（不晋升空集、拒绝删除最后一个测试点） |
| cases_revision | INT | NOT NULL DEFAULT 0 | 集合写操作自增计数（预留并发 CAS） |
| pending_verified | BOOLEAN | NOT NULL DEFAULT false | 暂存集已通过验题、待显式应用（任何新的暂存写入即清除） |
| time_limit_ms | INT | NOT NULL DEFAULT 1000 | 时间限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算有效限制，见 `judge.md`「语言限制换算」） |
| memory_limit_mb | INT | NOT NULL DEFAULT 256 | 内存限制（**C++ 基准**；其他语言按 `sandbox_configs` 语言比例换算，并受 `memory_min_mb` 下限约束） |
| difficulty | INT | NULL, CHECK (NULL OR >= 0) | 难度分（出题人 / 管理角色手动填写，类似 Codeforces；NULL=未评分；只约束非负，不设上限） |
| team_id | UUID | NULL, FK → teams.id | 归属团队；NULL=全站题目，非 NULL=团队题目（永久归属该团队，不进入公开题库） |
| owner_id | UUID | NOT NULL, FK → users.id | 创建者 |
| visibility | VARCHAR(16) | NOT NULL DEFAULT 'public' | 全站题目：`private` / `public`；团队题目：`admin_visible` / `team_visible` |
| status | VARCHAR(16) | NOT NULL DEFAULT 'draft' | `draft` 草稿 / `published` 已发布 / `archived` 已下线归档 |
| verified_at | TIMESTAMPTZ | NULL | 验题通过时间；「已验题」≡ 本字段非空（原 `is_verified` 列冗余已移除，API 字段由后端派生输出） |
| verified_by | UUID | NULL, FK → users.id | 验题通过审核人 |
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
CHECK (status <> 'published' OR verified_at IS NOT NULL)
```

索引：INDEX(`owner_id`)、INDEX(`team_id`, `visibility`, `status`)、INDEX(`visibility`, `status`)、GIN(`title` gin_trgm_ops)

### `problem_counters` — 题目统计计数表

与 `problems` 1:1（PK 即 FK，`ON DELETE CASCADE`）；判题终态时 upsert 原子累加，
避免判题高频写打在 `problems` 热行上。存量数据由迁移一次性回填。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| problem_id | UUID | PK, FK → problems.id (CASCADE) | |
| submission_count | INT | NOT NULL DEFAULT 0 | 终态提交数（统计口径见 `judge.md`：排除 verify 与 pending/judging/system_error） |
| accepted_count | INT | NOT NULL DEFAULT 0 | AC 提交数（同口径） |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | 最近累加时间 |

- 写入：判题落库时单条 `INSERT ... ON CONFLICT (problem_id) DO UPDATE ... + 1`（并发安全，计数行自动创建）
- 读取：题目列表 / 详情返回 `submission_count` / `accepted_count` 原始计数，无计数行按 0；通过率由前端按 `accepted_count / submission_count` 现算（无提交显示 `--`）
- 漂移对账：`submissions` 按口径 GROUP BY 重算可随时全量校正（暂无自动调度）

### `problem_tags` / `problem_tag_relations` — 标签

- `problem_tags`：`name` UNIQUE、`color`、`status`（`active` / `archived`，默认 `active`）。主键 id，created_at / updated_at。
- `problem_tag_relations`：`problem_id` / `tag_id`；UNIQUE(`problem_id`, `tag_id`)。
- 标签由 admin 在后台维护（新增 / 改名改色 / 归档）；**归档不删除**：题目既有关联保留并继续展示，但归档标签不再出现在激活列表，也不能被新题目选择
- 题目打标：创建 / 编辑请求体携带 `tags: string[]`（≤8 个、去重），值为**激活状态的标签名**；包含未知或已归档标签名时返回 1001

### `test_cases` — 测试点表

测试点行**不可变版本化**：集合成员资格由 `problems.active_case_ids`（生效集，判题使用）与
`problems.pending_case_ids`（暂存集，编辑与验题对象）定义。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | 行身份永不变更、永不删除；历史判题结果外键恒有效 |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| name | VARCHAR(64) | NULL | 测试点名（如 case1） |
| input_oss_id | VARCHAR(512) | NOT NULL | 判题输入（MinIO 对象 key：`problems/{problem_id}/cases/{case_id}/input`） |
| expected_output_oss_id | VARCHAR(512) | NOT NULL | 判题期望输出（MinIO 对象 key） |
| origin_id | UUID | NULL, FK → test_cases.id | 内容改版时指向被取代的原始行；首版为 NULL |
| sort_order | INT | NOT NULL DEFAULT 0 | 顺序 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `sort_order`)

> - **行一经被任一列表引用即不可变**：改名 / 换内容一律新增行（origin_id 指回原行）
> - 保存 = 目标状态写入 pending 列表：未改动点沿用原 id（零拷贝），改动点为新行 id，
>   删除点不出现；验题通过单事务 `active := pending` 并清空，失败保留继续编辑
> - 被取代的旧行退役留档（不再属于任何列表），不做清理
> - **展示样例不落本表**：样例以字符串数组存于 `problems.samples`，仅用于题目详情页展示与自测，不参与正式判题。正式判题只使用 active 列表引用的测试点。

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
| GET | /problems | public / auth | 题库列表。默认（scope=all）题库中心仅 published+public；`scope=mine` 为管理视图（须登录）：创建者见自己全部题目，管理角色（admin/tutor/team_creator）见可管理范围全量，可叠加 `status` 过滤；列表项恒带 `needs_reverification` 字段（存在待验证测试点，或样例晚于最近验题通过时间；仅 `scope=mine` 视图有意义，其他场景恒为 `false`）；支持难度分闭区间筛选（未评分题目不落入任何区间，min>max 返回 1001）；列表项带 `difficulty` 与 `submission_count` / `accepted_count` | 分页/标签/关键字/scope/status/difficulty_min/difficulty_max | problem[] |
| GET | /problems/tags | public | 激活标签列表（打标选择器与列表筛选用，仅 `status='active'`） | - | tag[]（id/name/color） |
| GET | /admin/tags | admin | 标签管理全量列表（含已归档） | - | tag[] |
| POST | /admin/tags | admin | 新增标签（name 唯一，重复返回 1001） | name/color? | tag |
| PUT | /admin/tags/{id} | admin | 修改标签名称 / 颜色 | name?/color? | tag |
| POST | /admin/tags/{id}/archive | admin | 归档标签（关联保留、不再可选） | - | tag |
| GET | /problems/{id} | public/owner | 题目详情（按可见性过滤）；带 `difficulty` 与 `submission_count` / `accepted_count` | - | problem |
| POST | /problems | admin/tutor/team_creator/team_admin | 创建题目（公开/团队） | team_id?/title/.../tags?/visibility/limits/difficulty? | problem |
| PUT | /problems/{id} | admin/tutor/team_creator/team_admin | 编辑题目 | ...（`tags` 全量替换标签关联；`difficulty` 非负整数，缺省不改动） | problem |
| PUT | /problems/{id}/test-cases | admin/tutor/team_creator/team_admin | 全量替换**暂存集**测试点（出题不设分值；提交得分由判题服务端按通过比例派生，比赛计分随 contests 模块配置）；被替换内容的 MinIO 旧对象异步清理；生效集不动，验题通过后晋升 | cases[]（name?、input、expected_output、sort_order） | - |
| PATCH | /problems/{id}/test-cases | admin/tutor/team_creator/team_admin | 增量更新**暂存集**（前端编辑器按行 diff 只提交变化的行）：upserts 带 id 为修改（input/expected_output 缺省或 null = 内容不变，可仅改名 / 调序；传字符串则整体替换该侧内容，空字符串 = 显式清空——写入空对象、ossId 保持非空，两侧同时置空返回 1001；改动生成新行、origin_id 指回原行）、无 id 为新增（输入输出不能全空）；delete_ids 表示目标状态中不含该点；同一 id 不得同时出现在 upserts 与 delete_ids（1001），未知 id 返回 3001；被替换内容的 MinIO 旧对象异步清理。生效集在晋升前不受影响 | upserts[]（id?、name?、input?、expected_output?、sort_order?）/ delete_ids[] | cases[]（目标状态合并视图：未改动点沿用原 id，含内容与 staged 标记，供前端重置基线） |
| POST | /problems/{id}/test-cases/apply | admin/tutor/team_creator/team_admin | 显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦，点「保存」才生效）；无暂存改动返回 3002，未通过验题（`pending_verified=false`）返回 3002；任何新的暂存写入都会清除已验标记 | - | problem |
| PUT | /problems/{id}/samples | admin/tutor/team_creator/team_admin | 全量替换展示样例（写 `problems.samples`，同时更新 `samples_updated_at`；不上传 MinIO；仅解释变更同样更新时间戳触发重验口径） | samples[]（input、output、explanation?），≤10 组、input / output 各 ≤64KB、explanation ≤64KB | - |
| POST | /problems/{id}/verify | admin/tutor/team_creator/team_admin（发起）/ auth（提交验题代码） | 发起验题 / 提交验题代码（双模式请求体：`code+language` 为提交，否则为发起）；提交不限身份，`invite_token` 可选 | invite_expires_hours?/invite_token?/code?/language? | verification 或 submission_id |
| GET | /verify-invites/{token} | public | 解析验题邀请链接（数据源 Redis `verify_invite:{token}`；返回题面与样例供受邀人查看，不含正式测试点内容与题解；`expires_at` 由 TTL 推算） | - | {problem_id, problem_title, expires_at, background, description, input_description?, output_description?, note?, tags[], time_limit_ms, memory_limit_mb, samples[]} |
| POST | /problems/{id}/publish | admin/tutor/team_creator/team_admin | 发布（须验题通过 + active 测试点 ≥ 1 + `pending_case_ids` 为 NULL；存在暂存改动或样例晚于 verified_at 时返回 3002，须重新验题） | - | problem |
| POST | /problems/{id}/archive | admin/tutor/team_creator/team_admin | 下线归档 | - | problem |
| GET | /teams/{team_id}/problems | admin/tutor/team_creator/team_admin | 团队题库列表（随 teams 模块实现） | 分页/可见性 | problem[] |
| POST | /files/upload/avatar | auth（头像） | 头像上传（multipart → ossId） | file | ossId |
| POST | /files/upload/image | auth（公共图片，登录用户可用） | 题面插图上传（multipart → url），Markdown 编辑器以 `![](url)` 引用；详见 admin.md files 表 | file（≤5MB，JPG/PNG/WEBP/GIF） | ossId |

> 测试点与样例均不走独立上传接口：`PUT /problems/{id}/test-cases` 接收 UTF-8 的 `input` / `expected_output` 内容（每项 ≤5MB），由后端生成对象 key 并分别上传 `problems/{problem_id}/cases/{case_id}/input` 与 `/output`，回填双 ossId，**写入暂存集（验题通过后晋升生效）**；样例经 `PUT /problems/{id}/samples` 直接存库（≤10 组、单项各 ≤64KB），不上传 MinIO。不生成测试点归档 ZIP，前端 ZIP 只在浏览器内解压为内容。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 题目不存在 |
| 2003 | 403 | 题目不可见（草稿 / 私有 / 团队题目越权） |
| 3002 | 409 | 发布未验题通过 / 归档后编辑 |
| 1001 | 400 | 测试点文件类型或大小不符 |
| 3003 | 409 | 重复发起验题（已有 pending 记录） |

## 当前基础前端页面

前端已提供 `/problems` 题库列表（常驻分页：总数 + 页容量切换；搜索防抖兼容中文输入法）、`/problems/{id}` 题目详情、提交与轮询查看 `/submissions/{id}` 评测状态，以及 `/problems/new` 写题页面。写题页面题面 / 题目背景 / 输入输出说明 / 题面说明（可选，折叠展开） / 官方题解使用 Markdown 编辑器（md-editor-v3，编辑 + 按需分屏预览；存储仍为 Markdown 文本），题目背景为必填、渲染于题面之前，题面说明渲染于题面最后（未填写不渲染）。详情页为「题面 + 编辑器」可拖拽双栏布局：桌面端高度锁定为一屏、左右两栏独立滚动（题面过长时左栏内部滚动）、分隔条可拖拽调宽（比例持久化，双击复位），窄屏（<900px）自动上下堆叠；题目背景 / 题面 / 输入输出说明 / 题面说明 / 官方题解按 Markdown 渲染（markdown-it + DOMPurify，支持 KaTeX 公式 `$...$` / `$$...$$`），样例仍为等宽文本块并提供复制，每组样例下的样例解释（Markdown，选填）仅在有内容时渲染。编辑器语言切换不覆盖已写代码；提交判题前需经确认框二次确认。评测结果页轮询 2s 一次、上限约 5 分钟后停止自动刷新并提示手动刷新。写题页面支持手工输入测试点或导入 `1.in` / `1.out` 格式 ZIP；ZIP 仅在浏览器内解压并转为可编辑内容，不向前端暴露 MinIO 对象引用。

管理后台「题目管理」（`/admin/problems`）列表：**点击行即进入只读预览**（草稿 / 已发布 / 已归档一致，留在管理动线，不跳前台），编辑 / 查看提交 / 归档收敛在行内操作列；「查看提交」进入 `/admin/problems/{id}/submissions` 提交列表页（上下文路由，面包屑「管理后台 / 题目管理 / 提交列表」），经 `GET /problems/{id}/submissions` 分页查看该题**全员提交**（含提交人、状态、得分、耗时、内存、语言、提交类型与提交时间），支持状态页签、提交人昵称关键字与语言 / 提交类型（练习 / 比赛 / 验题）筛选；**点击行进入 `/admin/problems/{id}/submissions/{sid}` 评测详情**（状态 / 得分 / 耗时 / 内存、编译错误信息、代码与逐测试点明细，评测中自动轮询），详情经 `GET /problems/{id}/submissions/{sid}` 读取。非题目管理角色访问均被后端 2003 拦截。

## 关键流程 / 验收条件

1. **题目生命周期**：创建默认 `status='draft'` → 编辑 / 维护测试点 → 验题 → `publish`（`status='published'`，CHECK 强制 `is_verified`）→ `archive`（`status='archived'`）。被题单 / 比赛引用时不得物理删除，仅归档。
2. **验题时效**：题目内容（题面等）变更不影响验题有效性；**测试点存在暂存集（pending 非空，精确判定）或样例在最近一次验题通过后变更（`problems.samples_updated_at > verified_at`），则须重新走验题流程才能发布**——发布接口违反时返回 3002；`scope=mine` 列表与详情分别以 `needs_reverification` 字段透出。测试点编辑只落暂存集，生效集（active）在晋升前不受影响，比赛中判题始终使用已验证的 active 集。
3. **验题**：发起 `POST /problems/{id}/verify`（生成邀请链接存 Redis，或不带参数创建空白记录）→ 任意登录用户提交代码（凭邀请链接或直接提交，身份不限）→ 系统按题目**暂存集（pending 为空时退化为生效集）**判题（复用 `submissions`，`submit_type='verify'`）→ 全部通过 → 仅打「已验待生效」标记（`pending_verified=true`，`case_status='verified'`）并回写 `problem_verifications.status='passed'`、判题链路回写 `verified_by / verified_at`（`verifier_id` 回写实际提交人）；**晋升与验题解耦**——管理角色调 `POST /problems/{id}/test-cases/apply` 显式生效后，单事务 `active_case_ids := pending_case_ids`、清空 pending（被取代旧行退役留档）。任何新的暂存写入都会清除已验标记。
4. **样例自测**：题目详情页展示样例字符串（`problems.samples` 数组）并提供复制；每组样例可附样例解释（`explanation`，Markdown，空则前端不渲染解释区块）；在线试运行能力规划由判题节点侧专用端点承担（当前后端不执行用户代码）。
5. **难度分与通过率**：难度分为出题人手动填写（`problems.difficulty`，非负整数，NULL=未评分），列表支持闭区间筛选；通过率统计由 `problem_counters` 承载，判题终态原子累加（口径见 `docs/contracts/judge.md`），API 返回原始计数、前端现算百分比。

## 明确不做

- 不物理删除题目；团队题目不设「升级公开」通道——公开题库仅来自全站题目（工作区 / admin 直出），团队是封闭空间
- 不支持 SPJ 特判：判题仅标准比对（忽略行尾空白与末尾换行、行内严格），无 checker 机制
- 不引入子任务 / 分组加权计分（见 `docs/architecture.md` 明确不使用）
- 测试点不向前端暴露下载 / 预签名 URL；提交结果不返回期望输出
- 不建验题邀请链接表（Redis 承载）与用户代码草稿表；AI 出题相关字段（`is_ai_generated` / `ai_generation_task_id`）随 AI 能力迭代再引入，当前不落库
- 不做 per-problem 语言级限制覆盖：题目限制为 C++ 基准，其他语言统一按 `sandbox_configs` 全局语言比例换算
- 难度分不做自动校准（不按通过率 / 用户 rating 自动折算）；通过率不落库为比率字段（由计数现算）；计数不做 Redis 缓存（单行 upsert 开销可忽略，漂移以 SQL 对账兜底）
