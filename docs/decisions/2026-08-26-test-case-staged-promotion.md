# 测试点暂存/生效双集合：problems 引用列表 + 题级状态

- 日期：2026-08-26
- 状态：已评审，实施中

## 背景

测试点修改目前即时生效：`patch_cases` 只拦归档题，已发布题目保存后判题立刻读到新点
（判题实时查 `test_cases` 表）。比赛中发现测试点有错时被迫「盲改」——新点有没有问题，
只有判了才知道，而一旦保存错误的新点，进行中的比赛立即被污染。
现有 `needs_reverification`（`MAX(test_cases.updated_at) > verified_at` 启发式）只是提示，
不阻断判题生效。

## 决策（最终采纳）

数据仍以 `test_cases` 行为准（身份、MinIO 引用、历史外键全部不动），行**不可变版本化**；
集合成员资格由 `problems` 上两个 id 引用列表定义：

### `problems` 新增列

| 列 | 说明 |
| --- | --- |
| `active_case_ids` JSONB NOT NULL DEFAULT '[]' | 生效集：判题唯一数据来源，元素为 test_cases.id |
| `pending_case_ids` JSONB NULL DEFAULT NULL | 暂存集：**NULL = 无暂存改动**；JSON 数组（含 `'[]'`）= 有暂存改动，内容即目标状态（区分「未编辑」与「编辑后删空」，消除空数组歧义） |
| `case_status` VARCHAR(16) NOT NULL | 题级状态缓存：`empty` 无测试点 / `to_verify` 待验题（active 空、pending 有）/ `to_reverify` 需重验 / `ok` 正常；与列表同事务维护 |
| `cases_revision` INT NOT NULL DEFAULT 0 | 集合每次写操作自增；预留并发 CAS |

### `test_cases` 新增列

| 列 | 说明 |
| --- | --- |
| `origin_id` UUID NULL, FK → test_cases.id | 内容改版时新行指向被取代的原始行；首版为 NULL |

### 不变式

1. 行一经被任一列表引用即为**不可变**：改名 / 换内容一律新增行（`origin_id` 指回原行），
   任何行永不修改、永不删除——`submission_test_case_results.test_case_id` 历史关联永不断
2. 保存 = 计算**目标状态**写入 `pending_case_ids`：未改动点直接沿用原 id（零拷贝零新增行），
   改动点为新行 id，删除点不在列表中出现
3. 判题只读 `active_case_ids`；验题提交按 pending 集判（pending 为空时退化按 active 判，
   覆盖首次验题与「无改动重验」两种形态）
4. 验题通过：单事务 `active_case_ids := pending_case_ids`、`pending := '[]'`、
   `case_status='ok'`；验题失败保留 pending 继续编辑
5. 被新版本取代的旧行不再属于任何列表，自然退役留档（元数据级体积，不做清理）
6. **生效集非空后永不为空**：拒绝晋升空集；「删除最后一个测试点」保存被拒绝
   （须先补新点或归档题目）；判定集为空时拒绝提交验题——杜绝「空 pending 退化判
   active 再晋升空集」导致的生效集意外擦除路径

### 题级状态推导（case_status 为其缓存）

| active | pending | 状态 |
| --- | --- | --- |
| 空 | NULL（无改动） | `empty`（发布门禁拦截） |
| 空 | 非 NULL | `to_verify`（首验） |
| 非空 | NULL（无改动） | `ok` |
| 非空 | 非 NULL（含 `'[]'` 全删） | `to_reverify` |

> 由不变式 6，生效集一旦非空永不灭失，故恒有：`is_verified ≡ active_case_ids 非空`。
> 该事实仍以 `verified_at` 为权威载体（时间戳本身必须存：样例比对与展示均依赖），
> 移除冗余列 `is_verified` 作为独立后续小步。

### 门禁与缓存

- 发布条件精确化：active ≥ 1 **且 pending 为空**；`needs_reverification` = pending 非空
  （替代 `MAX(updated_at) > verified_at` 启发式；样例仍按 `samples_updated_at` 时间戳比对）
- `data_version` 指纹 = sha256(数量 | 最大 updated_at)，**按判定集计算**：
  练习 / 比赛 = 生效集，验题提交 = 暂存集（NULL 退化生效集）。暂存编辑不影响生效集
  指纹（练习/比赛的节点缓存不失效），晋升瞬间自然失效并拉新，机制复用

## 讨论过的替代方案

1. **双 JSON 存内容 / ossId 全量副本**：外键断链、判题取数与门禁全量重写、双份数据同步，
   否决；评审中演化为「存 id 引用」后成立，即本决策
2. **`test_cases` 加行级 status 列（pending/active/superseded）**：技术等价，判题读取为
   单谓词更简，但需要影子行复制未改动点的元数据；最终选择题级列表版——选集表达直观、
   未改动点零成本沿用、晋升语义（换指针）更贴合「生效集」直觉。两者均为可行实现，
   本记录存档备查

## 修订（2026-08-26 同日，实施中采纳）

1. **验题与晋升解耦**：验题通过不再自动晋升，仅打 `pending_verified=true` 标记
   （新状态 `case_status='verified'` 已验待生效）；管理角色调新增端点
   `POST /problems/{id}/test-cases/apply` 显式生效（点「保存」才晋升）。
   任何新的暂存写入清除已验标记。动机：验题归验题，生效时机由出题人掌控。
2. **移除冗余列 `problems.is_verified`**：「已验题」≡ `verified_at IS NOT NULL`
   （两者恒同写同值）；CHECK 约束改写为 `status <> 'published' OR verified_at IS NOT NULL`，
   API 的 is_verified 字段改为模型派生属性、输出形状不变。
3. **判定集分流明确化**：练习 / 比赛恒判生效集；仅验题提交判暂存集——未验证的暂存
   改动绝不影响正常判题。FetchProblemData 按节点请求的 data_version 精确匹配候选集。

## 后果

- 正向：比赛中改点不再即时生效，生效集永远是「验过的」；未改动点跨编辑会话稳定复用；
  历史逐点明细完整可溯
- 负向：门禁 / 回读 / 判题取数从纯表谓词改为「解析列表 + IN 查询」；同一题并发编辑为
  整列表读改写（后写覆盖先写，`cases_revision` 预留 CAS，当前单管理员场景接受）；
  编辑器对「已被目标状态移除但仍生效中的点」不展示（以目标状态为准的一致性语义）
- 中立：MinIO 对象 key 格式、URL、gRPC 协议不变；存量迁移一次性回填
  （active 列表 = 现有全部行、case_status='ok'）
