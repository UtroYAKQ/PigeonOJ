# 判题节点 gRPC 网关（取代 Celery）

## 状态

已采纳（2026-08-23）。替代同日早先的「Celery 队列 + 心跳」方案。

## 背景

本地/远程判题节点需要部署在任意服务器上。原 Celery 方案要求节点能直连中心 Redis broker，
存在 broker 暴露面、消息重复投递竞态（unacked 还原 vs beat 重派）、以及 asyncio 与
Celery prefork 模型的持续摩擦（循环隔离、engine.dispose 等补丁）。

## 决策

- **移除 Celery**：删除 `app/worker.py`、`tasks.py`、broker/result 后端配置与 compose 依赖。
- **节点网关协议（gRPC 双向流）**：`protos/pigeonoj/judge/v1/judge.proto` 为机器可读契约。
  节点出站连接后端 `:50051`，首条 Register 凭令牌认证；服务端经同一流下发 SubmitJob，
  节点回传 JudgeResult；FetchProblemData 按 data_version 流式同步题目数据并缓存于容器 /cache。
- **负载均衡在后端**：注册表按 in-flight 最少优先选节点；无在线节点时提交保持 pending，
  由 FastAPI lifespan 内的维护循环每 30s 重扫重派（Redis SETNX 防并发重复）。
- **原子认领**：build_job_bundle 以 `UPDATE ... WHERE status='pending'` 认领，
  从根上消除双执行竞态（不再依赖幂等兜底作为唯一防线）。
- **节点封装为 Docker**：`src/judge/Dockerfile` 产出 pigeonoj/judge-node 镜像
  （nsjail + 三语言工具链 + grpcio）；宿主机工作区挂载 /sandbox、缓存挂载 /cache；
  privileged 仅用于 nsjail 嵌套 namespace（受控节点信任边界）。
- 目录重组：判题域代码独立为 `src/judge/`（node 守护进程、sandbox 基础镜像、镜像打包）。

## 后果

- 架构组件减少：无 broker、无 beat、无队列路由表；提交→派发→执行全链路一条流。
- 节点并发由自身 Semaphore 控制（capacity），不再受进程池模型限制。
- 断线即离线：in-flight 提交自动回收重派；数据缓存跨重启复用降低带宽。
- 执行核心在 `src/judge/node/executor.py` 与后端 `app/modules/judge/worker.py`
  存在同源副本，需人工保持一致（文件头已注明）。

## 内存判定实现（2026-08-23 补充）

- nsjail 命令行注入 `--rlimit_as=<有效内存MB>`（java21 例外：JVM 虚拟预留大，不施加 AS 封顶，
  靠 OutOfMemoryError 特征识别），超内存分配被内核直接拒绝。
- 失败特征判 MLE：stderr 含 `MemoryError / std::bad_alloc / OutOfMemoryError /
  Cannot allocate memory` 且退出码非 0 → `memory_limit_exceeded`。
- 另有 /proc 进程树 RSS 采样（10ms）作为展示参考值；嵌套 PID namespace 下
  对短命/快速分配进程可能低估，不影响判定正确性。
