# 判题节点调度架构

## 状态

已采纳（2026-08-23，在 2026-08-18-codeforces-style-judge-architecture 基础上落地实现）。

## 决策

### 节点模型

每个 Judge Worker 进程即一个沙箱节点：

- 启动时以 `JUDGE_NODE_ID`（缺省 `{hostname}-{pid}`）注册，持续向 Redis `sandbox:node:<id>` 写心跳 JSON
  （id / name / status / load / running_tasks / capacity / version / last_heartbeat_at）。
- 心跳 TTL = 3 × `JUDGE_HEARTBEAT_INTERVAL_SECONDS`（默认 30s），过期自动离线——不维护显式下线状态表。
- 负载 = 进程内 running_tasks 计数 / `JUDGE_NODE_CAPACITY`。

### 队列路由与降级

- 节点专属队列命名 `judge:<node_id>`；worker 以 `-Q judge:<id>,celery` 同时消费专属队列与共享队列。
- API 提交后调用 `dispatch_submission`：在线节点按 running_tasks 最小优先投递专属队列；
  **无在线节点回退共享队列 celery**——保证冷启动 / 本地单人开发零配置可用。
- 同名任务 `judge_submission` 在任意队列语义一致；投递失败不阻塞提交（提交保持 pending 由 beat 兜底）。

### 宕机兜底

- beat 每 60s 执行 `requeue_stuck_submissions`：pending > 5min 或 judging > 10min 的提交重置为 pending 并重新调度；
  Redis SETNX（TTL 10min）防止并发重复投递。判题写入幂等（(submission_id, test_case_id) upsert），重复执行安全。

### 生效限制与频控

- 语言白名单与启停来自 `sandbox_configs`（迁移 0004 含三语言种子：cpp17 基准、python ×3/×2/min128、java ×2/×2/min256）。
- 有效限制 = C++ 基准 × time_ratio / max(× memory_ratio, memory_min_mb)，output_limit_kb / cpu_cores / process_limit 一并生效。
- 提交频控：user+problem 冷却（4001）、全局并发上限（4002，阈值取系统配置 sandbox.judge_concurrency，
  在途计数 = 各节点 running_tasks 之和 + 共享队列执行中计数）。

## 后果与边界

- CPU/内存实时占用率字段暂报 0，待判题容器接入 cgroup 指标上报；内存判据仍按契约以峰值 RSS 为准。
- 共享队列兜底意味着「节点列表」不含未注册 worker；管理后台沙箱状态页仅展示已注册节点。
- Windows 本地 worker 必须 `-P solo`（单并发）；容量参数对 solo 池无意义但保持接口一致。

## 实现期修复的跨进程坑（2026-08-23 E2E 联调发现）

worker 是长驻进程且每个任务用独立 `asyncio.run` 循环，两个全局单例因此踩坑：

1. **aioredis 单例绑死首个循环**：`get_redis()` 改为按事件循环隔离（`shared/redis.py`），
   循环切换时重建客户端；否则第二个任务起报 "attached to a different loop"。
2. **SQLAlchemy async 引擎连接池跨循环**：任务协程结束时必须 `engine.dispose()`，
   否则池内 asyncpg 连接随旧循环关闭，下一任务 ping 报 `NoneType.send`
   （`tasks.py` 的 `_judge_submission / _requeue_stuck` 均在 finally 中回收）。
3. 函数级 `from app.config import get_settings` 在拆分 wrapper/inner 后遗留作用域错误，
   已提升为模块级导入。

结论：**修改后端代码后必须重启 Judge Worker 窗口**（Celery 无热重载），仅 uvicorn 有 --reload。
