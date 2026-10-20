# 比赛榜单与滚榜

本功能按账号排名；一个账号可代表一支参赛队。团队空间仍是比赛的组织和权限范围，不合并多个账号的提交。

## 使用入口

在比赛详情的榜单页打开「实时循环榜单大屏」。在管理员或团队比赛的「赛时工具」中，可打开以下页面：

| 模式 | URL 查询参数 | 用途 |
| --- | --- | --- |
| 实时榜 | `mode=live` | 每 15 秒轮询，自动循环滚动全部选手；滚动可独立暂停和调速 |
| 本机预览 | `mode=local`（默认） | 管理员在同一大屏操作、投屏；单步、回退、播放、暂停、1/2/4 倍速与重播 |
| 同步控制台 | `mode=control` | 准备持久化会话并控制多个观众页面；可直接在这一页投屏 |
| 观众大屏 | `mode=watch` | 仅显示服务端已揭晓的进度，刷新和断线后自动恢复 |

URL 示例：`/scrollboard.html?contest_id=<比赛 UUID>&mode=control`。团队空间入口额外携带 `team_id`；新的会话接口仍以比赛本身的团队归属在服务端鉴权。观众通过控制台的「打开观众大屏」按钮或同一 URL 的 `mode=watch` 打开。各设备须自行登录本站，保留现有比赛可见性；访问令牌不写入 URL。

大屏提供中英文、明暗主题、全屏、键盘空格播放/暂停及左右键单步/回退。长队名省略并提供完整提示，题目多时横向滚动，表头固定。切换后台页会暂停请求和本机播放计时，重新激活后恢复；同步模式的服务端时钟继续走。

## 比赛、封榜与揭晓

计分事实源是本场 `submit_type=contest AND is_after_contest=false` 的提交，报名但未提交的账号也显示。`contest_rankings` 是兼容的物化投影，Redis 是读缓存。实时榜、冻结榜、手动解冻与滚榜终局使用同一纯函数引擎。

- ACM：按 `(created_at, submission_id)` 排序，首次 AC 的提交时刻距开赛的整分钟数，加此前错误提交数乘配置罚时系数。AC 后的错误、重复 AC、系统错误、补题均不改变该题罚时。判题完成时刻不参与计分。
- IOI：每题历史最高分；已通过标志与首次通过时刻按提交顺序确定。系统错误、等待中与判题中的提交不计分。
- 排序保持项目口径：ACM 通过数降序、罚时升序；IOI 总分降序、通过数降序；之后昵称 Unicode 码点序、稳定用户 UUID。名次使用连续序号。前后端比较规则相同。
- 封榜统计边界为配置的 `freeze_time`（旧数据仅在缺失时回退 `frozen_at`）。`frozen_at` 记录周期任务的实际执行时间。任务延迟不会扩大公开时间窗；到达配置时刻的榜单读请求就按冻结口径返回。
- 冻结榜保留边界之前的已公开成绩，只在仍有隐藏提交的题格附上 `pending` 数和问号。封榜前交题在封榜后才判完的结果仍进入公开部分。已公开 ACM AC 不会被后续提交改成问号。
- 揭晓从**当前**还有待揭晓提交的最末选手开始，按该选手提交顺序揭晓一次、重新计分和排序，再选择新的最末选手。不会以最终名次预排选手。每一步携带完整的结果题格 `cell`，回退与追赶丢帧均由快照确定性重建。

只有比赛实际结束且正式提交均已离开 pending/judging 后，才可准备滚榜或正式解冻。系统错误不计为错误罚时，也不阻塞准备。比赛结束不自动解冻；播放、重播和播放完毕也不解冻。正式公布仍使用赛时工具的「解冻榜单」。

未正式解冻时，其他选手的提交列表、详情与单格成功提交查询保持关闭，避免从其他入口绕过悬念；比赛管理者继续拥有原有访问权限。赛后本人仍可读取自己的提交详情。普通比赛提交记录在解冻后按原来的赛后窗口开放；团队比赛始终叠加成员校验。

## 同步会话与接口

统一前缀 `/api/v1`，统一响应信封 `{code,message,data}`。

| 方法 | 路径 | 权限与行为 |
| --- | --- | --- |
| GET | `/contests/{id}/scoreboard-show` | 比赛管理者的完整预览包：`base_rows/final_rows/steps`，赛后且判题已结算 |
| POST | `/contests/{id}/scoreboard-session` | 比赛管理者创建会话；重复调用返回同一快照和进度 |
| GET | `/contests/{id}/scoreboard-session` | 已登录且有比赛可见权限的观众读取当前公开投影 |
| POST | `/contests/{id}/scoreboard-session/commands` | 比赛管理者控制，需携带 `revision/command_id/action` |

命令体示例：

```json
{"revision":0,"command_id":"11111111-1111-4111-8111-111111111111","action":"play","speed":1}
```

`action` 为 `play/pause/next/previous/restart/speed/prepare`，`speed` 为 1、2 或 4。

- `scoreboard_sessions` 每场比赛一行，存储快照 JSONB、版本 UUID（主键）、revision、cursor、playing、speed、anchor_at、last_command_id 与创建时间。约束为 contest_id 唯一、非负进度、速度枚举；外键级联仅随比赛删除。
- 写操作使用数据库行锁并检查 revision；过期命令返回 HTTP 409 / code 3002。重复的最后一条 command_id 不重复执行。并发管理员只能有一个相同 revision 的新命令生效。
- 自动进度由服务端 UTC 时钟计算：`cursor + floor((now-anchor_at)*speed/1.8秒)`，上限为总步数。GET 计算投影，不依赖浏览器写回、不落库推进，因此控制台关闭或服务重启后仍可恢复。显式操作时才物化进度并增加 revision。
- 观众响应包含 `id/revision/cursor/total_steps/playing/speed/server_time/can_control/problems/rows/current_step` 和比赛基本信息。绝不包含 snapshot、final_rows 或未来 steps。观众页不会请求完整预览端点。
- 同步页使用约 0.225–0.75 秒短轮询，倍速越高轮询越密；失联时保留已有画面，显示错误并重连。多屏最终显示同一服务端状态，画面更新时间受各自网络和轮询时刻影响，不承诺逐帧同时。
- 后续重判不会悄悄修改已准备快照。控制台的「重新准备数据」需明确确认，会校验比赛已结算，换新版本 UUID、增加 revision 并重置全部大屏进度。本机预览重新打开时读取当前数据；共享重播仅重播当前版本。
- 重播/回退只改变当前展示，已经公开的信息不会重新保密。新快照和重播均不改变正式比赛是否解冻。

错误：未登录 401；无管理/团队查看权限 403 / 2003；无会话 404 / 3001；赛中、尚在判题或 revision 冲突 409 / 3002；非法命令和速度由请求模型拒绝。

## 验证

根目录 `.venv` 安装仓库既有后端依赖，`src/frontend` 执行 `npm ci`。测试数据库与 Redis 必须独立于开发数据，遵循 operations.md 的测试隔离规则。

```powershell
# 仓库根目录
.venv/Scripts/python src/backend/scripts/check_import_rules.py
# src/backend 目录，设置隔离 TEST_DATABASE_URL / REDIS_URL 后
../../.venv/Scripts/python -m pytest tests/test_contests.py tests/test_scoreboard_sessions.py tests/test_scoreboard_engine.py
# src/frontend 目录
npm run lint:check
npm test
npm run test:scoreboard
npm run build
```

`test:scoreboard` 调用后端纯函数生成真实 Schema 的 ACM/IOI/无隐藏提交/无选手夹具，在 jsdom 执行真实大屏脚本，检查终局逐格一致、题号映射、控制、多个观众与刷新恢复；也支持 `-- --fixture=<JSON>`。不需要数据库、Redis、沙箱或外网服务。界面静态资源走 `public/` 随 Vite 复制，独立于应用壳。

部署前执行 Alembic `upgrade head`（新增迁移 0039）；旧榜单接口增加 `problems/generated_at`，题格增加 `pending`，步骤增加 `cell`。此分支没有更换技术栈或引入推送服务。

榜单与观众投影的题目元信息仅包含 problem_id/letter/score/sort_order，不包含私有题目标题。赛前非管理者读取榜单返回空榜，不带题目列。`total_steps` 不通过裁掉隐藏 AC 后的无效提交而缩短：这些步骤保持计分不变，避免用总步数提前推断早期 AC。旧版缺少 generated_at 的永久缓存会被自动忽略并重算。
