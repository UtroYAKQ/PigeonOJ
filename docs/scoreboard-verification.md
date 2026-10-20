# 榜单与滚榜交付验证

日期：2026-10-20。基础版本：main `da3287c0a2e38e7238fcf31982825bb928729f62`；功能分支：`feat/scoreboard-live-resolver`。

## 变更摘要

在现有比赛和封榜功能上，增加实时循环展示、本机投屏预览、共享控制台与多个观众大屏。统一计分和封榜边界，修复判题完成时间影响罚时、仅封榜后参赛者缺席、题格键值错误、回放终局不一致等问题。

## 代码变更

- `services/scoreboard.py`：统一 ACM/IOI 聚合、稳定排序、当前末位选手揭晓、逐格完整状态与回放。
- `services/contest.py`：以正式提交为事实源，封榜保留已公开成绩，处理晚到/重复/乱序判题和旧缓存；补齐零提交账号。
- `scoreboard_sessions` 与迁移 0039：持久化快照、revision、共享播放时钟和幂等命令；观众读取仅公开投影。
- `public/scrollboard.html` 与 scoreboard.js/core.js/css：四种大屏模式、中英文、明暗、全屏、回退、播放/暂停/调速及循环展示。静态模块使用 .js 扩展名以沿用生产 Nginx 的 JavaScript MIME 配置。
- 比赛详情和赛时工具提供入口；未正式发布时，服务端与 UI 同步限制他人提交结果入口，保持团队权限隔离。
- 原始开发提示词保存在 `docs/prompts/scoreboard-enhancement.md`，使用方法与端点契约见 `docs/scoreboard.md`。

## 文档同步检查

| 文档 | 状态 | 内容 |
| --- | --- | --- |
| architecture.md | 已更新 | 保持轮询、共享时钟和计分事实源 |
| security.md | 已更新 | 管理命令、公开投影、未解冻记录与团队隔离 |
| contracts/contests.md | 已更新 | 封榜边界、统一计分、字段与新增端点 |
| operations.md | 已更新 | 迁移、测试、轮询与运行约定 |
| frontend.md | 已更新 | 独立页面、字典、主题与生命周期 |

## 验证结果

| 检查 | 结果 |
| --- | --- |
| `check_import_rules.py` | 通过，97 个应用文件 |
| 后端：contests / scoreboard_sessions / scoreboard_engine / team_space / judge_dispatch | **68 passed** |
| 前端 `npm run lint:check` | 通过 |
| 前端 `npm test` | **44 passed**，11 个测试文件 |
| `npm run test:scoreboard` | 6 组通过：ACM 71 步、IOI 96 步、无隐藏提交、无选手、控制台与双观众重连、实时滚动控制 |
| `npm run build` | 通过 |
| Alembic 空库升级至 0039 → 回退 0038 → 再升级 0039 | 通过，独立 PostgreSQL 数据库 |
| 实际 Edge 浏览器 | 桌面 1600×900、手机 390×844、中英与明暗主题、揭晓操作通过；无页面 JavaScript 错误 |
| Git 补丁空白检查（保留仓库原有 CRLF 约定） | 通过 |

测试覆盖提交时间罚时、同时间稳定排序、零提交和封榜后首次提交、AC 后提交不改计分、重播终局一致、服务端自动推进、重复命令、并发 revision 冲突、刷新恢复、重新准备版本、普通用户与跨团队越权、隐藏结果保护和赛前题目列隐藏。

## 验证范围与运行说明

后端使用独立 PostgreSQL 16 测试库，Redis 接口由本机 fakeredis 2.40.0 的 TCP 服务模拟；没有连接或修改开发/生产数据库。Edge 界面测试使用后端生成的真实 Schema 夹具拦截 API 请求。完整 Docker Compose、真实 Redis 7、真实沙箱执行与生产并发负载未在本次环境中复验。构建保留既有大体积 vendor chunk 提示；pytest 的两条警告为 ORM TestCase 类不作为测试类收集。

部署时先运行 `alembic upgrade head`。观众沿用平台登录和比赛可见性；多屏同步通过短轮询收敛到同一服务端进度，受各自网络延迟影响。播放完成仍需管理员明确「解冻榜单」才正式发布成绩。重判后可由控制台明确确认「重新准备数据」创建新快照。
