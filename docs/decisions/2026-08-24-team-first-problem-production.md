# 出题入口收敛管理后台；团队封闭出题；移除升级公开与 SPJ

- 日期：2026-08-24
- 状态：已采纳（分阶段实施）

## 背景

现行契约为「双轨」出题：admin/tutor 可直出全站题目（`team_id=NULL`），team_creator/team_admin 可出团队题目；团队题经 `promote` 升级公开（不可逆、无审核）。问题：

1. 出题入口挂在题库中心（segment 切换器 + 详情页三点菜单），管理界面混入前台浏览动线；
2. 团队题可无审核直达公开题库，公海无编辑准入闸门；
3. SPJ checker 链路（上传、proto 传输、沙箱内编译执行）维护成本高，而当前题型不需要特判。

团队模块尚未实现，tutor 直出链路已建成可用；SPJ 与 promote 在代码中已有存量实现（见 Phase 3 清理清单）。

## 决策

1. **出题入口唯一：管理后台**。admin/tutor 在管理后台出全站题（`team_id=NULL`），验题通过后发布进入公开题库。前台（题库中心 / 题目详情 / 评测结果）为纯消费界面，不出现任何管理与创作入口。
   - 迁移内容：「题目管理」视图自题库中心 segment 切换器迁入管理后台菜单；`/admin` 区域进入权限放宽为 `admin/tutor`（staff 会话），侧栏按角色过滤——tutor 仅见「题目管理」，admin 见全部；创建 / 编辑 / 草稿管理作为其上下文页面随迁（`breadcrumbParent` 指向管理后台层级）；题目详情三点菜单的「草稿管理」入口移除，统一由管理工作台行操作进入。
2. **团队封闭出题**：team_creator/team_admin 在团队空间出团队题（`visibility='admin_visible' / 'team_visible'`），不提供任何进入公开题库的通道。`POST /problems/{id}/promote` 与 `promoted_at` 已从契约整体移除。公开题库的唯一来源是管理后台直出的全站题。
3. **移除 SPJ**：删除 `problems.spj` / `spj_code` 字段、`POST /files/upload/spj` 端点与判题链路 checker 逻辑；判题统一标准比对（忽略行尾空白与末尾换行、行内严格）。
4. **角色集合不变**：全局 `admin/tutor/user` + 团队 `team_creator/team_admin/team_member` 共 6 个。变化仅一处：`/admin` 壳的进入门槛由「仅 admin」放宽为「admin 或 tutor」，页面内功能仍按 `meta.roles` 过滤。
5. **存量兼容**：既有全站题保留原状与 `owner_id` 编辑 / 归档权；存量 `spj=true` 题目经迁移下线字段后按标准比对判题。

## 原因

- 学生视角的前台零管理噪音；管理者视角的全部操作集中在一个有明确边界（侧栏整体切换 + 「返回前台」）的区域，两侧认知模型都最简单；
- 复用既有应用壳的空间切换设计（进入 `/admin` 后侧栏换管理菜单），不需要发明任何新概念或新视图形态；
- 团队定位为封闭训练 / 协作空间，「是否进公海」的审批闸门没有服务对象，直接取消通道比维护审批流更简单；
- SPJ 是一条长链路（上传校验 → 对象存储 → gRPC 传输 → 节点编译 → 每测试点独立 nsjail 调用），当前收益为零，先删后加的成本远低于长期空转维护。

## 替代方案

- **个人工作区 / 聚合创作工作台**：被否决——为新场景引入新概念与聚合视图，抬高了认知与实现成本；管理后台壳已足以承载出题。
- **promote 申请-审批制 / 无审核直通**：均被否决——前者逐题审批负担重，后者公海无质量闸门；团队转封闭后两者皆失去服务对象。
- **`team_author` 中间团队角色**：被否决——角色集合保持 6 个（见 `2026-08-15-rbac-simplification.md`）。
- **保留 SPJ 以备将来**：被否决——无现实题型需求，需求出现时凭本记录重新立项。

## 影响（分阶段实施）

1. **Phase 0（文档，已完成）**：`docs/contracts/problems.md` 移除 promote 端点 / `promoted_at` / 团队 `public` 可见性 / SPJ 字段与端点及错误码描述；`judge.md`、`architecture.md` 移除 SPJ 相关条目。待随实施同步：`teams.md`（团队出题为封闭空间的说明）、`ai.md`（AI 出题归属）、`frontend.md`（Phase 2 时重写「题库信息架构」与「管理后台空间」节）。
2. **Phase 1（增量）**：实现 teams 模块本体（契约已备好），团队出题走 `GET/POST /teams/{id}/problems` 通道，天然封闭。
3. **Phase 2（前端迁移）**：「题目管理」及其上下文页面迁入 `/admin`；`/admin` 守卫放宽为 `admin/tutor`；题库中心移除 segment 切换器与一切管理入口；详情页移除草稿管理入口；同步修订 `frontend.md`。
4. **Phase 3（代码清理，破坏点，单独 commit 可回滚）**：
   - Alembic 迁移：drop `problems.spj` / `spj_code` / `promoted_at`，收紧可见性 CHECK 约束；
   - 删除 `POST /problems/{id}/promote` 路由与服务方法、`POST /files/upload/spj` 端点及 FileService 上传逻辑、judge jobs/gateway/node daemon 的 checker 分支；
   - proto `SubmitJob.spj` 字段按 gRPC 兼容方式废弃（保留字段号，停止赋值），重新生成 stub；
   - 前端移除写题页 SPJ 表单区、列表 / 详情页 SPJ 标签、`api/files.ts` 上传函数与 i18n 词条；
   - 更新 `tests/test_problems.py` 的 promote 用例为「404 不存在」，补 SPJ 字段拒绝写入用例。
