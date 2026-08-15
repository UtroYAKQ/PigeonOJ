# 社区模块契约

> 站内通知、私信、题解、讨论区、评论与举报。

## 数据模型

### `notifications` — 站内通知表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 接收者 |
| type | VARCHAR(32) | NOT NULL | `team_apply` / `team_approval` / `contest` / `system` 等 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NULL | |
| related_type | VARCHAR(32) | NULL | 关联对象类型 |
| related_id | UUID | NULL | 关联对象 ID |
| is_read | BOOLEAN | NOT NULL DEFAULT false | |
| read_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`user_id`, `is_read`, `created_at DESC`)

### `messages` — 站内消息表（私信）

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| sender_id | UUID | NOT NULL, FK → users.id | 发送者 |
| receiver_id | UUID | NOT NULL, FK → users.id | 接收者 |
| content | TEXT | NOT NULL | |
| is_read | BOOLEAN | NOT NULL DEFAULT false | |
| read_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`receiver_id`, `is_read`, `created_at`)

### `solutions` — 用户题解表

区别于题目表的官方 `solution` 字段。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| problem_id | UUID | NOT NULL, FK → problems.id | |
| user_id | UUID | NOT NULL, FK → users.id | 作者 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NOT NULL | 题解正文（Markdown） |
| status | VARCHAR(16) | NOT NULL DEFAULT 'published' | `draft` / `published` / `removed` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`problem_id`, `status`)

### `posts` — 讨论区帖子表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | 发帖人 |
| title | VARCHAR(255) | NOT NULL | |
| content | TEXT | NOT NULL | Markdown |
| category | VARCHAR(32) | NULL | 板块 / 分类 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'published' | `published` / `removed` |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`status`, `created_at DESC`)

### `comments` — 评论表

支持对题目、题解、帖子等对象的评论与回复。

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| user_id | UUID | NOT NULL, FK → users.id | |
| target_type | VARCHAR(32) | NOT NULL | `problem` / `solution` / `post` / `submission` |
| target_id | UUID | NOT NULL | 目标对象 ID |
| parent_id | UUID | NULL, FK → comments.id | 回复的父评论 |
| content | TEXT | NOT NULL | |
| is_deleted | BOOLEAN | NOT NULL DEFAULT false | 删除（软） |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`target_type`, `target_id`, `created_at`)、INDEX(`parent_id`)

### `reports` — 举报表

| 字段 | 类型 | 约束/默认 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | |
| reporter_id | UUID | NOT NULL, FK → users.id | 举报人 |
| target_type | VARCHAR(32) | NOT NULL | `problem` / `solution` / `post` / `comment` / `user` |
| target_id | UUID | NOT NULL | |
| reason | TEXT | NOT NULL | 举报理由 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'pending' | `pending` / `handled` / `ignored` |
| handled_by | UUID | NULL, FK → users.id | 处理人 |
| handled_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

索引：INDEX(`status`, `created_at`)

## 数据所有权

- 通知按接收者隔离：所有查询必须带 `WHERE user_id = ?`（接收者）；标记已读仅本人可操作
- 私信：只能读自己的收发消息（`sender_id = ?` 或 `receiver_id = ?`）
- 题解 / 帖子：草稿仅作者可见；已发布内容公开可见；作者可下架（`status='removed'`）
- 评论软删除（`is_deleted=true`），不物理删除
- 举报人身份不向被举报方暴露
- 管理操作（下架他人内容、处理举报）仅 `admin`

## 端点

统一前缀 `/api/v1`。

| 方法 | 路径 | 权限 | 说明 | 关键入参 | 关键出参 |
| --- | --- | --- | --- | --- | --- |
| GET | /notifications | auth | 我的通知列表 | 分页/已读 | notification[] |
| POST | /notifications/{id}/read | owner | 标记已读 | - | - |
| GET | /messages | auth | 私信列表 | 分页 | message[] |
| POST | /messages | auth | 发送私信 | receiver_id, content | - |
| GET | /solutions | public | 题解列表（published） | 分页/problem_id | solution[] |
| POST | /solutions | auth | 发布题解 | problem_id, title, content | solution |
| PUT | /solutions/{id} | owner | 编辑题解 | ... | solution |
| GET | /posts | public | 讨论区列表（published） | 分页/category | post[] |
| POST | /posts | auth | 发帖 | title, content, category | post |
| GET / PUT | /posts/{id} | owner/admin | 帖子详情 / 下架 | - | post |
| GET | /comments | public | 评论列表（按 target） | target_type, target_id | comment[] |
| POST | /comments | auth | 发表评论 / 回复 | target_type, target_id, parent_id?, content | comment |
| DELETE | /comments/{id} | owner/admin | 删除评论（软） | - | - |
| POST | /reports | auth | 举报 | target_type, target_id, reason | - |
| GET | /admin/reports | admin | 举报列表 / 处理 | 分页/状态 | report[] |

## 错误码

| 错误码 | HTTP | 说明 |
| --- | --- | --- |
| 3001 | 404 | 通知 / 消息 / 题解 / 帖子 / 评论 / 举报不存在 |
| 2003 | 403 | 越权操作他人内容（非 owner / admin） |
| 3002 | 409 | 目标对象不存在或已下架（发布评论 / 回复时） |

## 关键流程 / 验收条件

1. **通知**：业务事件（团队申请 / 审批 / 比赛）写入接收者通知；接收者查询列表、标记已读。
2. **私信**：发送者 → 接收者消息记录；接收者查询自己的收发消息并标记已读。
3. **题解 / 帖子**：作者发布（默认 `published`）→ 他人浏览；作者或 `admin` 下架（`removed`）。
4. **评论 / 回复**：评论可回复（`parent_id`），软删除；下架目标后其评论不再对外展示。
5. **举报**：`auth` 用户举报 → `admin` 处理（`handled` / `ignored`）。

## 明确不做

- 评论物理删除（软删除，保留审计）
- 社区功能开关（通知 / 消息 / 评论 / 题解 / 讨论区）由系统配置控制（见 `admin.md`）
