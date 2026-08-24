# 决策：题目发布三步流拆分为三个独立页面；优化路由跳转与全局文案

- 日期：2026-08-25
- 影响范围：管理后台出题动线（路由 / 视图拆分）、路由器 scrollBehavior、i18n 文案

## 背景

原实现把「基础信息与题面 → 样例与测试点 → 验题与发布」做在单个 `ProblemCreateView.vue` 内部（`step` ref + `n-steps`），存在以下问题：

- 刷新页面回到第 1 步，无法直达某一步；
- 步骤间跳转不经路由，浏览器前进 / 后退语义混乱（新建后 `router.replace` 曾引发组件重挂载问题）;
- 单文件 500+ 行，三种状态机耦合，维护成本高。

## 决策

1. **一步一页**：

   | 步骤 | 路由 | 组件 |
   | --- | --- | --- |
   | 新建入口（第 1 步） | `/admin/problems/new` | `ProblemStatementView.vue` |
   | 第 1 步 编辑题面 | `/admin/problems/:id/edit/statement` | `ProblemStatementView.vue` |
   | 第 2 步 样例与测试点 | `/admin/problems/:id/edit/cases` | `ProblemCasesView.vue` |
   | 第 3 步 验题与发布 | `/admin/problems/:id/edit/verify` | `ProblemVerifyView.vue` |

2. **跳转语义**：
   - 新建保存成功后 `router.replace` 进入 `/edit/cases`——后退不会回到 `/new` 二次建草稿；编辑态步骤间用 `push`，后退自然回上一步；
   - 旧链接 `/admin/problems/:id/edit` 以 route redirect 兼容到 `/edit/statement`；
   - 每页头部「取消」回管理工作台；第 3 步底部提供「完成，返回列表」（未发布离开时草稿保留）。
3. **自动保存边界不变**：仍是「下一步」触发持久化；空白测试点行不提交、内容签名一致跳过上传；进入第 3 步前要求至少一个非空正式测试点。
4. **路由体验**：createRouter 增加 `scrollBehavior: () => ({ top: 0 })`，跨页导航回到页顶。
5. **文案**：向导按钮改为「保存并下一步」；校验提示给出可执行动作（如「请至少配置一个正式测试点（输入、输出不能同时为空）」）；common 兜底错误统一带「请稍后重试」指引。

## 否决的替代方案

- **保持单文件 + 查询参数同步步骤**（`?step=2`）：仍是一个巨型组件，且查询参数与内部状态易失同步；
- **步骤可点击任意跳步**：第 2/3 步依赖前序数据落库，允许跳步会产生「未保存题面就配测试点」的中间态，故仅保留线性导航。

## 后果

- `ProblemCreateView.vue` 删除；引用它的文档以本记录与新路由为准；
- 三页各自加载所需数据（题面表单 / 测试点快照 / 完整详情），`can_manage` 校验在每个编辑页独立执行，越权访问统一弹错并回管理工作台。
