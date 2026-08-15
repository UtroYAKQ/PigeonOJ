# 判题 / 沙箱模块契约

> 提交、判题调度、判题结果与沙箱安全执行环境。判题器执行规范见文末，是沙箱实现消除歧义的依据。

## 数据模型

### `submissions` — 代码提交表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| contest_id | UUID | NULL, FK → contests.id | 比赛提交时关联（submit_type='contest'） |
| verification_id | UUID | NULL, FK → problem_verifications.id | 验题提交时关联（submit_type='verify'） |
| submit_type | VARCHAR(16) | NOT NULL DEFAULT 'practice' | `practice` 练习 / `contest` 比赛 / `verify` 验题 |
| language | VARCHAR(32) | NOT NULL | `python3.12` / `cpp17` / `java21` |
| code | TEXT | NOT NULL | 提交代码（应用层按 UTF-8 字节校验 ≤ 64KB，超出拒绝） |
| status | VARCHAR(24) | NOT NULL DEFAULT 'pending' | `pending` / `judging` / `accepted` / `wrong_answer` / `time_limit_exceeded` / `memory_limit_exceeded` / `output_limit_exceeded` / `runtime_error` / `compile_error` / `system_error` |
| score | INT | NOT NULL DEFAULT 0 | 总得分（IOI） |
| time_used_ms | INT | NULL | 最大用时 |
| memory_used_kb | INT | NULL | 最大内存 |
| error_message | TEXT | NULL | 编译错误 / 运行错误信息 |
| is_after_contest | BOOLEAN | NOT NULL DEFAULT false | 是否赛后补题提交 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `problem_id`, `created_at DESC`)、INDEX(`contest_id`, `user_id`)、INDEX(`verification_id`)、INDEX(`problem_id`, `status`)、INDEX(`status`)

CHECK 约束：

```sql
CHECK (
  (submit_type = 'practice' AND contest_id IS NULL AND verification_id IS NULL) OR
  (submit_type = 'contest'  AND contest_id IS NOT NULL AND verification_id IS NULL) OR
  (submit_type = 'verify'   AND verification_id IS NOT NULL AND contest_id IS NULL)
)
```

### `submission_test_case_results` — 提交测试点结果表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| submission_id | UUID | NOT NULL, FK → submissions.id | |
| test_case_id | UUID | NULL, FK → test_cases.id | 对应测试点 |
| status | VARCHAR(24) | NOT NULL | 单测试点判题状态 |
| time_used_ms | INT | NULL | |
| memory_used_kb | INT | NULL | |
| score | INT | NOT NULL DEFAULT 0 | 该测试点得分 |
| output | TEXT | NULL | 运行输出（MinIO ossId，正文截断后落对象存储） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：

- UNIQUE(`submission_id`, `test_case_id`) WHERE `test_case_id IS NOT NULL`
- INDEX(`test_case_id`)

> 仅记录运行输出（`output`），不记录、不返回测试点期望输出（`expected_output`），防止用户反推判题答案。

### `sandbox_configs` — 沙箱配置表

按语言配置安全执行环境的运行参数。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| language | VARCHAR(32) | NOT NULL, UNIQUE | `python3.12` / `cpp17` / `java21` |
| cpu_limit | INT | NULL | CPU 时间上限（ms，与 `problems.time_limit_ms` 口径一致；核数上限由 `cpu_cores` 单独表达） |
| time_ratio | REAL | NOT NULL DEFAULT 1.0 | 时间比例：有效时间 = `problems.time_limit_ms` × 本值（cpp17=1.0，基准） |
| memory_ratio | REAL | NOT NULL DEFAULT 1.0 | 内存比例：有效内存 = `problems.memory_limit_mb` × 本值（cpp17=1.0，基准） |
| memory_min_mb | INT | NOT NULL DEFAULT 0 | 有效内存下限（如 Java JVM 固定基准开销；有效内存取比例换算值与下限的较大者） |
| process_limit | INT | NULL | 进程数限制 |
| filesystem_readonly | BOOLEAN | NOT NULL DEFAULT true | 文件系统只读 |
| output_limit_kb | INT | NULL | 程序输出大小上限（KB），超出判定 `output_limit_exceeded` 并截断 |
| disk_quota_mb | INT | NULL | 沙箱临时可写目录磁盘配额 |
| cpu_cores | INT | NULL | 可用 CPU 核数上限（限制多线程占用） |
| network_enabled | BOOLEAN | NOT NULL DEFAULT false | 是否允许沙箱内网络访问（默认禁止，防 SSRF/外联） |
| is_enabled | BOOLEAN | NOT NULL DEFAULT true | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

> `problems.memory_limit_mb` / `time_limit_ms` 为 **C++ 基准**限制；判题时按本语言的 `time_ratio` / `memory_ratio` / `memory_min_mb` 换算出有效限制（见下方「语言限制换算」），沙箱按有效限制执行，本表不直接存题目限制绝对值。沙箱节点实例运行时状态（在线 / 离线 / 负载 / 健康检查）为热数据存 Redis（`sandbox:node:<id>`），不落库。

## 数据所有权

- 用户只能读自己的提交历史（`WHERE user_id = ?`）；提交详情 `owner` 可见
- 提交结果不返回测试点期望输出（`expected_output`）
- 沙箱执行日志作为子记录按 `request_id` 归入 `request_logs.extra`，不单独建日志表
- AI 自测（改代码后运行、AI 出题校验样例）走内联样例执行接口，不落 `submissions`

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /submissions | auth | 提交判题 | problem_id, language, code, submit_type, contest_id?/verification_id? | submission_id |
| GET | /submissions/{id} | owner | 提交详情 | - | submission + case_results[] |
| GET | /submissions | auth | 提交历史 | problem_id/contest_id/status | submission[] |
| POST | /sandbox/sample-run | auth | 测试样例执行（内联） | code, language, input, expected_output? | actual_output, passed, time_used_ms, memory_used_kb, compile_error? |
| GET | /sandbox/health | admin | 沙箱节点健康 | - | nodes[{id, status, load}] |

> **提交校验**：语言须在 `sandbox_configs` 白名单且启用；代码大小上限 64KB（UTF-8 字节）；按 user+problem 提交冷却 + 全局并发上限做 Redis 频控。
> **提交越权校验**：`submit_type=contest` 时 `contest_id` 由服务端从当前请求上下文推导（已报名 + 比赛进行中 + 本人），不信任客户端传入；`submit_type=verify` 须校验 `verification` 记录的 `verifier_id` 与当前用户一致。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 1001 | 400 | 语言不在白名单 / 代码大小超 64KB |
| 3001 | 404 | 提交不存在 / 题目不存在 |
| 3002 | 409 | 提交状态冲突（如对已结束比赛提交非补题） |
| 4001 | 429 | 提交冷却中（user+problem 冷却期未过） |
| 4002 | 429 | 全局判题并发上限触发排队 / 拒绝 |
| 5001 | 502 | 上游沙箱执行失败 |

## 判题流程（Celery 驱动）

```
用户提交代码
  → API 创建 submissions(status=pending)
  → Celery enqueue (judge_submission, submission_id)
  → 沙箱调度器按语言/资源/可用实例分配执行节点
  → 沙箱按题目 C++ 基准限制 × 语言比例的有效限制编译运行
  → 逐测试点判题，写 submission_test_case_results
  → 汇总写 submissions(status/score/time/memory)
  → 触发下游：比赛榜单更新(contest_rankings)、用户状态更新
```

要点：

- 提交统一按 `submit_type` 区分场景：练习（默认）、比赛（`contest_id` 关联，含赛后补题）、验题（`verification_id` 关联，结果驱动 `problem_verifications.status`；验题通过同步回写 `problems.is_verified / verified_by / verified_at`）。
- 队列由 Celery 承担，`sandbox_configs` 提供语言级运行参数（含输出大小、磁盘配额、CPU 核数、网络开关）与判题限制比例；`problems` 提供 **C++ 基准**内存 / 时间限制，判题按提交语言解析有效限制。
- 判题比对模式：`problems.spj=false` 时默认比对（忽略行尾空白与末尾换行、行内严格）；`problems.spj=true` 时 SPJ checker 在沙箱内编译运行判定，checker 同样受沙箱资源限制。
- 输出超限：程序输出超过沙箱输出上限时截断比对，判定 `output_limit_exceeded`，不再继续比对剩余输出。
- 判题失败（沙箱异常、超时）自动重试，超过阈值转 `system_error`。
- 判题结果仅返回用户程序输出与判定状态，不返回测试点期望输出。
- AI 自测走内联样例执行接口，不落 `submissions`。

## 语言限制换算

题目限制以 **C++ 为基准**（`problems.time_limit_ms / memory_limit_mb` 即 C++ 限制），其他语言按 `sandbox_configs` 语言级比例换算（提交时解析，快照进判题链路）：

- 有效时间 = `problems.time_limit_ms × time_ratio`（向下取整）
- 有效内存 = `max(problems.memory_limit_mb × memory_ratio, memory_min_mb)`
- `cpp17` 比例固定 1.0（基准）；`java21` / `python3.12` 用平台默认比例，可在 `sandbox_configs` 调整
- Java `-Xmx` 按有效内存换算（运行时参数），判据仍为 RSS 峰值
- 比例是全局语言级配置，不做 per-problem 覆盖（见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
- 题目详情页可展示各语言有效限制（前端按语言比例派生，不存库）

## 判题器执行规范

| 项 | 规范 |
| --- | --- |
| 时间测量 | wall-clock 与 CPU 时间双限：任一超有效时间限制（`time_limit_ms × time_ratio`）即判 `time_limit_exceeded` |
| 内存测量 | 以进程峰值常驻内存（RSS，含子进程）为口径，超有效内存限制（`max(memory_limit_mb × memory_ratio, memory_min_mb)`）判 `memory_limit_exceeded`；Java 以 RSS 为准（不把 `-Xmx` 堆上限当判据），`-Xmx` 按有效内存换算、仅作运行时参数 |
| 入口约定 | 三种语言统一入口：C++ `Main.cpp`、Java 主类固定 `Main`、Python `Main.py`，判题器据此拼接编译 / 运行命令 |
| 编译命令 | cpp17：`g++ -std=c++17 -O2 -o Main Main.cpp`；java21：`javac Main.java`；python3.12：免编译 |
| 运行命令 | cpp17：`./Main`；java21：`java -Xmx<堆上限> Main`（堆上限由有效内存换算，仅运行时用）；python3.12：`python3.12 Main.py` |
| 标准流 | 逐测试点独立运行：测试点输入重定向 stdin，stdout 捕获为程序输出（写入 `submission_test_case_results.output`） |
| 默认比对 | 忽略行尾空白与末尾换行、行内严格 |
| SPJ 契约 | checker 编译 / 运行命令同 cpp17，进程参数：`checker <input文件> <answer文件> <output文件>`；退出码 0=AC、非 0=WA（其它非零退出可映射为 `system_error` 供排障）；checker 受沙箱资源限制 |
| 输出上限 | 程序输出超出 `sandbox_configs.output_limit_kb` 截断并判 `output_limit_exceeded` |

> 上表为文档约定；实际编译 / 运行命令以 `sandbox_configs` 语言级配置为准，沙箱节点按配置拼接，所有执行均在 nsjail 隔离内完成。

## 测试样例执行接口（内联）

```
调用方（用户或 AI）
  → POST /sandbox/sample-run { code, language, input, expected_output? }
  → 沙箱编译并运行，返回实际输出
  → 若有 expected_output 则做比对，返回 passed
  → 样例数据全部内联传入，不读取数据库/对象存储的测试点文件
```

适用场景：用户编辑器「试运行样例」自测、AI 修改代码后自测、AI 出题生成样例后校验样例正确性。

## 明确不做

- 不单独建判题日志表（明细在 `submission_test_case_results` + `submissions`，沙箱日志归入 `request_logs.extra`）
- 不单独建验题判题表（验题复用 `submissions`，`submit_type='verify'`）
- 沙箱默认禁止网络访问，不提供例外开关（SSRF 防护）
- 测试点对象不向前端暴露下载 / 预签名 URL（判题节点独立只读账号内部拉取）
- 不做 per-problem 语言级限制覆盖（C++ 基准 + `sandbox_configs` 全局语言比例即可，见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
