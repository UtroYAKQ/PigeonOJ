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
| score | INT | NOT NULL DEFAULT 0 | 总得分（服务端派生：练习 / 验题按满分 100 均分到各测试点、仅通过计分；OI 比赛中以比赛配置的单题分值平摊到测试点，随 contests 模块实现） |
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
| test_case_id | UUID | NULL, FK → test_cases.id ON DELETE SET NULL | 对应测试点；测试点被替换 / 删除时置空，历史结果行保留（迁移 0010） |
| status | VARCHAR(24) | NOT NULL | 单测试点判题状态 |
| time_used_ms | INT | NULL | |
| memory_used_kb | INT | NULL | |
| score | INT | NOT NULL DEFAULT 0 | 该测试点得分（服务端派生：单点分值一致 = 单题满分 ÷ 测试点数，仅通过时计分；练习 / 验题满分为 100，OI 比赛为比赛配置的单题分值） |
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
- **后端进程不执行任何用户代码**：代码执行只发生在注册的判题节点容器内；
  样例 / 用户自测经网关派发到节点一次性运行，后端进程同样不经手代码执行

## 用户自测

题目详情页的轻量代码运行入口（「试运行」，不计分、不入提交记录）：

- **输入**：用户代码 + 编程语言 + 可选自定义 stdin（各 ≤64KB UTF-8 字节）
- **输出**：仅程序 stdout 与运行元信息（状态 / 耗时 / 内存 / 错误摘要）；无比对、无期望输出概念
- **每次独立**：单次运行互不影响，无测试用例列表管理，请求不落库、不写对象存储
- **限制换算**：以该题 `time_limit_ms` / `memory_limit_mb` 为基准按语言比例换算（防滥用口径），编译预算由节点按运行限制独立推导；与测试点无关
- **可见性**：与题目详情页同一规则（已发布 或 具备管理权限）；语言白名单取 `sandbox_configs` 且 `is_enabled`
- **频控**：user+problem 冷却（Redis `judge:selftest:` 前缀，时长复用 `sandbox.cooldown_seconds`；派发失败自动释放冷却槽）+ 全局并发上限（复用 `sandbox.judge_concurrency`，网关在途统计含自测）
- **生命周期**：作业仅存在于网关内存 pending 表（request_id 关联）；节点断线即时置错、整链路 120s 兜底超时，不参与维护循环重派

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| POST | /submissions | auth | 提交判题 | problem_id, language, code, submit_type, contest_id?/verification_id? | submission_id |
| GET | /submissions/{id} | owner | 提交详情（含代码、逐测试点明细 case_name + 状态/耗时/内存/得分/程序输出；不返回期望输出） | - | submission（含 restricted 标志） |
| GET | /submissions | auth | 提交历史（本人，`WHERE user_id=?`） | problem_id/contest_id/status/分页 | submission[]（含 restricted 标志） |
| POST | /problems/{id}/run-code | auth | 用户自测（单次运行，不落库不计分；见「用户自测」节） | language, code, input? | status, output(stdout), error_message?, time_used_ms, memory_used_kb? |
| GET | /sandbox/health | admin | 沙箱节点健康 | - | nodes[{id, status, load}] |

> **得分可见性（ACM 赛制限分）**：`submit_type=contest` 且关联比赛 `rule_type=ACM` 且 `end_time` 未到时，详情与列表接口的 `restricted=true`、`score=null`、`cases=[]`（服务端扣数据，前端仅做条件渲染）；IOI 赛制 / 练习 / 验题 / 比赛结束（含赛后补题）恒为完整可见。contests 模块落地前无比赛数据，恒为 `restricted=false`。策略实现在 `SubmissionService.is_score_restricted`。

> **提交校验**：语言须在 `sandbox_configs` 白名单且启用；代码大小上限 64KB（UTF-8 字节）；按 user+problem 提交冷却 + 全局并发上限做 Redis 频控。
> **提交越权校验**：`submit_type=contest` 时 `contest_id` 由服务端从当前请求上下文推导（已报名 + 比赛进行中 + 本人），不信任客户端传入；`submit_type=verify` 须校验 `verification` 记录的 `verifier_id` 与当前用户一致。

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 1001 | 400 | 语言不在白名单 / 代码或自测输入大小超 64KB |
| 3001 | 404 | 提交不存在 / 题目不存在 |
| 3002 | 409 | 提交状态冲突（如对已结束比赛提交非补题） |
| 4001 | 429 | 提交冷却中（user+problem 冷却期未过；含用户自测冷却） |
| 4002 | 429 | 全局判题并发上限触发排队 / 拒绝（统计口径含用户自测） |
| 5001 | 502 | 上游沙箱执行失败（提交判题链路异常 / 自测无在线节点或节点超时） |

## 判题流程（gRPC 节点网关，已实现；无 Celery）

```
用户提交代码
  → API 创建 submissions(status=pending)
    · 语言白名单取 sandbox_configs 且 is_enabled
    · user+problem 冷却（4001）与全局并发上限（4002），阈值来自系统配置 sandbox 域
  → dispatch_submission：网关注册表按任务数（判题 + 自测）最少优先选节点；
    build_job_bundle 原子认领（UPDATE ... WHERE status='pending'）后经 gRPC 流推送 SubmitJob
  → 无在线节点：保持 pending，网关维护循环每 30s 重扫派发
节点（pigeonoj/judge-node 容器，privileged，出站连接后端 :50051）
  → 数据缓存未命中时 FetchProblemData 拉取测试点（data_version 缓存于容器 /cache）
  → 按 sandbox_configs 比例换算有效限制（时间 ×time_ratio；内存 max(×memory_ratio, memory_min_mb)）
  → nsjail 原生编译一次、逐测试点独立运行，写 submission_test_case_results（输出落 MinIO）
  → 回传 JudgeResult；汇总写 submissions；验题提交回写 verification 与 problems.is_verified
维护循环兜底：pending>60s / judging>5min 重置重派（Redis SETNX 防并发重复投递）
```

### 节点网关协议

`.proto` 契约见 `protos/pigeonoj/judge/v1/judge.proto`（机器可读契约，stub 已生成入库于
`app/rpc/gen` 与 `src/judge/node/gen`）：

- `Connect(stream NodeMessage) returns (stream ServerMessage)`：节点生命周期主通道。
  首条 Register 携带令牌（后端 `JUDGE_GATEWAY_TOKENS` 其一），不符即 UNAUTHENTICATED；
  上行 Heartbeat / JudgeResult / RunCodeResult，下行 SubmitJob / RunCodeJob / CancelJob(预留)。
- `FetchProblemData(ProblemDataRequest) returns (stream FileChunk)`：
  按 `data_version` 流式传输 manifest / cases/<id>.in|.out；
  令牌经 metadata `x-node-token` 携带。数据指纹 = sha256(测试点数量|最大 updated_at)，
  **按判定集统计**：练习 / 比赛 = 生效集（`problems.active_case_ids`），
  验题 = 暂存集（`pending_case_ids`，NULL 时退化生效集）；暂存编辑不影响生效集指纹，
  晋升瞬间自然失效（见 `docs/decisions/2026-08-26-test-case-staged-promotion.md`），
  节点按 `<problem_id>-<data_version>` 缓存于容器 `/cache`，跨提交复用。
- 断线语义：连接断开即离线，其名下 in-flight 提交由服务端重置 pending 并重派，
  在途用户自测请求（pending Future）即时置错返回；判题写入幂等，重复执行安全。

**RunCodeJob / RunCodeResult（用户自测）**：网关 `dispatch_run_code` 按负载最低节点派发
单次运行作业（request_id 关联、代码内联、自定义 stdin 内联、限制已换算），在节点队列推入
`run_code` 消息后挂 pending Future 等待节点沿流回传；结果不落库，仅透传给发起请求。
节点复用正式判题的「编译一次 + 单点运行」执行路径（无比对阶段）。

### Judge Worker 边界

Judge 节点为长驻容器（`src/judge/Dockerfile`），执行核心与消息仅以 `submission_id` 为业务关联键。它经网关获取作业描述（代码内联、限制已换算、测试点仅元数据），通过 FetchProblemData 拉取数据文件到本地缓存；对 C++/Java 在编译阶段调用一次 nsjail 生成产物，随后每个测试点独立调用 nsjail 运行；Python 无编译阶段。节点将程序输出随结果回传，服务端存入 `submissions/{submission_id}/cases/{case_id}/output`，把测试点结果持久化到 `submission_test_case_results`，最后汇总更新 `submissions`。节点采集 stdout、stderr、退出码和资源数据，并在任务结束后清理临时目录。测试点期望输出只在判题节点与服务端内部流转，不进入公开响应；不接受用户可控 URL 或内联测试点 payload。


要点：

- 提交统一按 `submit_type` 区分场景：练习（默认）、比赛（`contest_id` 关联，含赛后补题）、验题（`verification_id` 关联，结果驱动 `problem_verifications.status`；验题通过同步回写 `problems.is_verified / verified_by / verified_at`）。
- 任务派发由 gRPC 网关承担，`sandbox_configs` 提供语言级运行参数（含输出大小、磁盘配额、CPU 核数、网络开关）与判题限制比例；`problems` 提供 **C++ 基准**内存 / 时间限制，判题按提交语言解析有效限制。
- 判题比对模式：统一默认比对（忽略行尾空白与末尾换行、行内严格）；不支持 SPJ 特判（见 `docs/decisions/2026-08-24-team-first-problem-production.md`）。
- 输出超限：程序输出超过沙箱输出上限时截断比对，判定 `output_limit_exceeded`，不再继续比对剩余输出。
- 判题失败（沙箱异常、超时）自动重试，超过阈值转 `system_error`。
- 判题结果仅返回用户程序输出与判定状态，不返回测试点期望输出。
- 后端进程不执行用户代码；用户自测经网关派发到节点一次性运行（见「用户自测」节）。

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
| 内存测量 | 以进程峰值常驻内存（RSS，含子进程）为口径，超有效内存限制（`max(memory_limit_mb × memory_ratio, memory_min_mb)`）判 `memory_limit_exceeded`；Java 以 RSS 为准（不把 `-Xmx` 堆上限当判据），`-Xmx` 按有效内存换算、仅作运行时参数。实现：nsjail 以 `--rlimit_as=<有效内存>` 硬性封顶地址空间（Java 例外，JVM 虚拟预留大，不施加），超限分配触发 MemoryError / bad_alloc 特征判 MLE；另有 /proc 树 RSS 采样作为展示参考值（嵌套 PID namespace 下对短命进程可能低估） |
| 入口约定 | 三种语言统一入口：C++ `Main.cpp`、Java 主类固定 `Main`、Python `Main.py`，判题器据此拼接编译 / 运行命令 |
| 编译命令 | cpp17：`g++ -std=c++17 -O2 -o Main Main.cpp`；java21：`javac Main.java`；python3.12：免编译 |
| 运行命令 | cpp17：`./Main`；java21：`java -Xmx<堆上限> Main`（堆上限由有效内存换算，仅运行时用）；python3.12：`python3.12 Main.py` |
| 标准流 | 逐测试点独立运行：测试点输入重定向 stdin，stdout 捕获为程序输出（写入 `submission_test_case_results.output`） |
| 默认比对 | 忽略行尾空白与末尾换行、行内严格 |
| stderr 归集 | 执行器过滤 nsjail 自身的 `[I]`/`[W]` 日志行后仅返回/记录程序真实错误输出；nsjail 的 `[E]`/`[F]` 故障行保留用于执行器排障 |
| 输出上限 | 程序输出超出 `sandbox_configs.output_limit_kb` 截断并判 `output_limit_exceeded` |
| 沙箱身份与临时目录 | nsjail 开启 `clone_newuser`，默认映射 `inside 0 ↔ outside 0`——jailed 进程当前具备全局 root 级文件访问（nsjail 启动日志有 [W] 提示）。作业目录仍统一按「属主 nobody(65534) + 0777」准备：同时兼容未来把映射收紧为真实 nobody、以及不给 root DAC 旁路的挂载层（如 Docker Desktop 文件共享）。jail 内挂载可写 tmpfs `/tmp`（64MB）与 `/dev/shm`（32MB），均 `mode=1777`、nodev/nosuid；**tmpfs 挂载必须位于 nsjail.cfg 挂载列表末尾**——nsjail 的 pivot_root 暂存树固定在 `/tmp/nsjail.root`，提前覆盖 `/tmp` 会破坏根文件系统组装。执行环境显式注入 `TMPDIR=/tmp` 与 `PYTHONDONTWRITEBYTECODE=1`；`rlimit_as` 基线为 16384 以容纳 JVM 虚拟地址预留（4096 会使 javac/JVM 启动即 OOM），C++ / Python 每次执行由执行器按题目内存限制动态覆盖 |

> 上表为文档约定；实际编译 / 运行命令以 `sandbox_configs` 语言级配置为准。判题节点负责准备与工作区 `/workspace` 挂载根一致的本地临时工作目录，并将容器内路径转换为 jail 内 `/workspace/<relative-job-path>` 的绝对路径；nsjail 执行器只接收受控 argv 和 jail 可见路径，不使用 shell 拼接。沙箱不访问 MinIO、数据库或公网，所有执行均在 nsjail 隔离内完成。

## 明确不做

- 不单独建判题日志表（明细在 `submission_test_case_results` + `submissions`，沙箱日志归入 `request_logs.extra`）
- 不单独建验题判题表（验题复用 `submissions`，`submit_type='verify'`）
- 沙箱默认禁止网络访问，不提供例外开关（SSRF 防护）；不提供用户可控 URL 执行接口，代码和测试点由判题节点从内部存储准备到本地临时目录
- **后端进程不执行任何用户代码**（无内联执行端点；用户自测经网关派发到节点 nsjail 执行，见「用户自测」节）
- 测试点对象不向前端暴露下载 / 预签名 URL（判题节点经网关认证后按 data_version 拉取）
- 不做 per-problem 语言级限制覆盖（C++ 基准 + `sandbox_configs` 全局语言比例即可，见 `docs/decisions/2026-08-15-language-limit-ratio.md`）
