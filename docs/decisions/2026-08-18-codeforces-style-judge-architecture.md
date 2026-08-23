# Codeforces 风格判题架构

## 状态

已采纳。

## 决策

PigeonOJ 采用「判题调度器 + 独立 Judge Worker + nsjail 执行器」的架构，不将沙箱设计为接收任意 URL 的公网代码执行 API。

```text
FastAPI
  → submissions(status=pending)
  → Celery judge_submission
  → Judge Worker
  → nsjail executor
  → submission_test_case_results
  → submissions 汇总状态
```

Judge Worker 负责从数据库和 MinIO 准备提交代码、测试输入和期望输出到本地临时工作目录；nsjail 只接收本地工作目录和动态资源限制，不直接访问 MinIO、数据库或公网。每个测试点独立运行，程序输出写入 MinIO，期望输出不返回前端。

## 原因

- API 服务不执行不可信代码，降低 Web 层被利用后的影响范围。
- 测试点和期望输出只在内部 Judge Worker 可见。
- Judge Worker 和沙箱节点可以独立扩容、摘除和重试。
- 与已有 Celery、Redis、MinIO、`submissions`、`submission_test_case_results` 和 `sandbox_configs` 契约一致。

## 约束

- 沙箱默认禁止网络，不接受用户可控的任意 URL。
- 任务消息只传 `submission_id` 或受服务端校验的任务引用，不传测试点期望输出。
- Judge Worker 必须清理每个任务的临时目录，并对编译和运行阶段分别施加超时与资源限制。
- 生产沙箱节点与 API / 数据库节点隔离；本地 Compose 的 `privileged` 仅用于受控开发验证。
