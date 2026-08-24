# 契约索引

> `docs/contracts/` 按模块拆分契约。改契约前先读本索引，定位目标模块对应的文件。

## 模块 → 文件

| 模块 | 契约文件 | 内容 |
| --- | --- | --- |
| 公共（所有模块） | [common.md](common.md) | 响应信封、通用错误码、分页契约 |
| 认证 / 用户 | [users.md](users.md) | `users`、`user_sessions`、认证与用户端点、冻结/封禁语义 |
| 团队 | [teams.md](teams.md) | `teams`、`team_members`、`team_member_applications`、团队与邀请端点 |
| 题库 | [problems.md](problems.md) | `problems`、`test_cases`、`problem_tags`、`problem_verifications`、题目端点 |
| 题单 | [problem-sets.md](problem-sets.md) | `problem_sets`、`problem_set_items`、题单端点 |
| 比赛 | [contests.md](contests.md) | `contests`、`contest_problems`、`contest_registrations`、`contest_rankings`、比赛端点 |
| 判题 / 沙箱 | [judge.md](judge.md) | `submissions`、`submission_test_case_results`、`sandbox_configs`、提交 / 判题 / 沙箱端点、判题器执行规范 |
| 社区 | [community.md](community.md) | `notifications`、`messages`、`solutions`、`posts`、`comments`、`reports`、社区端点 |
| 管理 / 运维 | [admin.md](admin.md) | `system_configs`、`request_logs`、`login_logs`、`exception_logs`、管理端点 |

## 领域关系概览

```
users ─┬─< user_sessions
       ├─< user_roles >─ roles（scope='team' 时 object_id → teams）
       ├─< team_members >─ teams · team_member_applications
       ├─< problems (owner_id) · problem_sets (owner_id) · contests (owner_id)
       ├─< submissions
       └─< notifications · messages · posts · solutions · comments · reports

problems ─┬─< problem_tag_relations >─ problem_tags
          ├─< test_cases
          ├─< problem_verifications
          ├─< problem_set_items >─ problem_sets
          ├─< contest_problems >─ contests
          └─< submissions ─< submission_test_case_results

contests ─┬─< contest_problems · contest_registrations · contest_rankings
          └─< submissions
```

> `─<` 表示一对多；`>─` 表示多对一。Redis 侧不落盘：`email:code:<email>:<purpose>`（邮箱验证码）、`team:invite:<token>`（团队邀请链接）、`verify_invite:{token}`（验题邀请链接，见 problems.md）、`sandbox:node:<id>`（沙箱节点运行时状态）。

## AI 使用方式

1. 改哪个模块的 API / 数据模型 / 错误码，先读该模块对应的契约文件
2. 涉及信封、通用错误码、分页等跨模块约定，先读 `common.md`
3. 改权限 / 角色 / 可见性时，对照 `docs/architecture.md` 的权限设计与权限矩阵
4. **新增契约文件时，必须在本表新增一行**（并同步 `docs/workflow.md` 的同步映射表）

## 数据模型唯一来源

表结构以 `alembic/versions/` 下的迁移 SQL 为准（表名、字段、类型、索引、CHECK 约束）；各模块契约文件中的表结构是其文档化说明。改动表结构时必须同时：① 创建 Alembic 迁移（up/down）；② 更新对应契约文件。
