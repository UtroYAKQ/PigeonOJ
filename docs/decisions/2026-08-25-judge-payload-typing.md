# 判题链路进程内表示类型化 + 提交详情字段对齐契约

- 日期：2026-08-25
- 状态：已实施（纯实现层收口 + 一处 API 响应字段修正；不改变分层结构、gRPC 协议与表结构）

## 背景

判题链路的进程内边界表示存在三类问题：

1. **裸 dict 传递**：`build_job_bundle` 返回、`apply_job_result` 接收均为 `dict[str, Any]`，
   键名靠人工记忆，拼错只能运行时暴露；外层 dict 与内层 `ResourceLimits` dataclass 风格割裂。
2. **魔法值散落**：Redis 节点状态键前缀 `sandbox:node:` 在写入方（网关）与读取方（admin 服务）
   各写字面量；`x-node-token` metadata 键、心跳状态值 `"online"` 为行内硬编码；
   结果落库的状态兜底写死 `"system_error"` 字符串而同函数其他位置使用枚举。
3. **提交详情违反序列化规范且字段与契约不符**：`SubmissionService.get_detail`
   手写 dict 组装 cases 明细（refactoring-notes 第四节明确禁止），字段名为 `test_case_id`，
   而 `schemas/judge.TestCaseResult`、前端 `types/judge.ts` 与评测页表格列均期望 `case_name`
   ——前端「测试点名」列实际恒为空。

## 决策

1. **proto 是唯一线上契约，dataclass 只活在后端进程内**：
   - 派发方向：`JobBundle` + `TestCaseFile`（frozen dataclass，`build_job_bundle` 产出、
     `send_job` 逐字段序列化为 `judge_pb2.SubmitJob`）
   - 回传方向：`JudgeOutcome` + `CaseOutcome`（frozen dataclass，`_to_outcome` 从 proto 转换、
     `apply_job_result` 消费落库）
   - 不为 dataclass 建 Pydantic / ORM 映射：它们是 proto 与 Repository 方法签名之间的临时适配表示，
     无持久化、无复用消费方
2. **魔法值收敛为命名常量**：`SANDBOX_NODE_KEY_PREFIX` 定义于 `core/redis.py`
   （写入方 judge_gateway 与读取方 services/admin 共用）；`_NODE_TOKEN_METADATA_KEY`、
   `_NODE_STATUS_ONLINE` / `_CHANNEL_GATEWAY` 定义于 judge_gateway；状态兜底改用
   `SubmissionStatus.SYSTEM_ERROR` 枚举成员
3. **提交详情改为 Pydantic 组装**：新增 `schemas/judge.SubmissionDetailOut`
   （`SubmissionDetail` + `cases: list[TestCaseResult]`），service 按 `TestCase.id → name`
   批量补出 `case_name`，路由直接 `model_dump(mode="json")`

## 后果

- 正向：键名获得 IDE 补全与 mypy 静态检查；契约三处重复（proto / dataclass / DB 写入签名）
  收敛为两处；前端评测页「测试点名」列恢复数据
- **API 响应形状变更（接受）**：`GET /submissions/{id}` 的 `cases[]` 明细中
  `test_case_id` 被 `case_name` 取代。前端类型定义本就声明 `case_name` 且未引用
  `test_case_id`，无需改动即受益；契约文档已同步（contracts/judge.md 端点表）
- 中立：URL、表结构、gRPC 协议、环境变量全部不变
