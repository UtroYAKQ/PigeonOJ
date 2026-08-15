# 判题限制：C++ 基准 + 全局语言比例

- 日期：2026-08-15
- 状态：已采纳

## 背景

同一道题用不同语言提交，时间 / 内存表现差异大：C++≈1×、Java 约 2–3× 且带 JVM 固定内存基准开销、Python 约 3–5×。题目 `time_limit_ms / memory_limit_mb` 是单一值，对所有语言一视同仁——按 C++ 调，则 Java / Python 的合理算法也易 TLE / MLE；按 Python 调，则 C++ 过于宽松、训练信号弱。需要为「同一题、不同语言、不同限制」定一个模型。

## 决策

以 **C++ 为基准语言**：`problems.time_limit_ms / memory_limit_mb` 即 C++ 的限制（题目设置的时间 / 空间都是针对 C++）。`sandbox_configs` 每语言新增三个字段承载比例与下限：

- `time_ratio`（REAL，默认 1.0，`cpp17`=1.0）
- `memory_ratio`（REAL，默认 1.0，`cpp17`=1.0）
- `memory_min_mb`（INT，默认 0）—— Java JVM 固定基准开销的兜底下限

判题时按提交语言解析有效限制：

- 有效时间 = `time_limit_ms × time_ratio`
- 有效内存 = `max(memory_limit_mb × memory_ratio, memory_min_mb)`
- Java `-Xmx` 按有效内存换算（运行时参数），判据仍为 RSS 峰值

不做 per-problem 语言级覆盖（列入「明确不做」），后续按需演进。

## 原因

- 支持语言少（3 种）且相对性能稳定，全局比例一个旋钮即可覆盖绝大多数公平性问题，出题人填一组 C++ 限制即可，零额外成本
- 复用现有按语言唯一的 `sandbox_configs`，不加新表、不加 `system_configs` 条目，结构最简
- Java 有固定内存基准（JVM 启动即占数百 MB），纯倍数换算不成立，故用 `memory_min_mb` 兜底
- 基准语义单一（C++），判题器与出题人理解成本最低

## 替代方案

- **per-problem 覆盖表 `problem_language_limits`**：最精确，但出题人每题需配多组值、编辑 UI 复杂，MVP 收益低——列为演进路径
- **题目表加语言列**（`time_limit_cpp / _java / _python`）：语言增多时列爆炸，弃
- **统一放宽限制**（按最慢语言调）：C++ 过松、训练信号弱，弃

## 影响

- `problems.time_limit_ms / memory_limit_mb` 语义明确为 **C++ 基准**（见 `docs/contracts/problems.md`）
- `sandbox_configs` 新增 `time_ratio / memory_ratio / memory_min_mb` 三列，判题器按提交语言解析有效限制（见 `docs/contracts/judge.md`「语言限制换算」）
- 题目详情页可按语言展示有效限制（前端侧派生，不存库）
- 若未来出现某题语言比例不适用的场景，再引入 per-problem 覆盖表（本决策不排除该演进）
