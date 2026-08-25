# 测试点增量更新：前端按行 diff + PATCH 端点 + 详情内容回读

- 日期：2026-08-25
- 状态：已实施

## 背景

测试点编辑此前只有「全量替换」一条路（`PUT /problems/{id}/test-cases`）：
前端对整份列表做签名对比，任何一行变化都触发删除全部 + 重传全部。三个连带问题：

1. 无谓开销：只改一个测试点也要重传所有文件（每项 ≤2MB）
2. 历史断层：未改动的测试点 id 全部更换，历史判题结果失去关联
   （0010 迁移已把外键改为 ON DELETE SET NULL 保住结果行，但关联信息仍丢失）
3. 详情回读缺失（既有 bug）：契约写明「管理角色读详情时回读测试点内容用于编辑」，
   实现却把 MinIO 对象 key 当作 `input / expected_output` 返回——编辑已有题目时文本框
   显示的是对象路径，整体保存会把 key 字符串当内容上传

## 决策

### 1. 新增 `PATCH /problems/{id}/test-cases`（增量语义）

| 输入 | 语义 |
| --- | --- |
| upserts 带 id | 修改该行：改名 / 调序 / 换内容；input / expected_output 留空 = 内容不变 |
| upserts 不带 id | 新增（输入输出不能全空） |
| delete_ids | 删除该行（MinIO 旧对象异步清理；历史判题结果保留、引用置空） |

- 仅被触碰的行 bump `updated_at`：未动行不改变 `MAX(test_cases.updated_at)`，
  因此不触发发布门禁的「需重新验题」（problems.md），也不使判题节点 data_version 缓存失效
- 校验：同一 id 不得同时出现在 upserts 与 delete_ids（1001）；未知 id 返回 3001；
  上传失败回滚已上传对象（与 replace_cases 同模式）
- 响应返回服务器权威全量列表（含内容与 id），前端据此重置本地行与基线快照
- PUT 全量替换保留（兼容与批量导入场景）；前端编辑器默认走 PATCH

### 2. 详情内容回读修复

`get_problem_detail` 的管理分支改经 `list_cases_with_contents()` 回读 MinIO 内容后返回
（仅 can_manage=true 时，与契约一致）；PATCH 路由复用同一方法产出响应。

### 3. 前端按行 diff（ProblemCasesView.vue）

- 加载详情时保留每行 `id` 并记录服务器基线快照（含内容）
- 保存时逐行对比基线：无 id（新增）、name/input/expected_output 变化、位置变化 → 进 upserts；
  基线存在但当前列表没有的行 → delete_ids；**delta 为空则不发任何请求**
- sort_order 只对被提交的行下发目标位置；顺序由相对位置表达，允许空洞
- 成功后用响应重置本地行与基线，后续空保存不再产生 delta

## 后果

- 正向：单行修改只上传该行文件；未动测试点的判题历史保留完整 id 关联；
  编辑已有题目不再出现对象 key 泄漏到文本框
- 负向（接受的代价）：管理角色读详情会拉取全部测试点内容（≤1000 × 2MB 上限，
  实际题目规模远小于此）；前端 diff 为纯展示层逻辑，需与后端语义保持同步（契约已写明）
- 中立：URL、表结构、gRPC 协议不变；全量 PUT 行为不变
