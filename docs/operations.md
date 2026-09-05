# 运行与运维

> 如何运行、测试、部署本项目；基础设施约定（Redis、调度、对象存储）。涉及配置或发布变更时先读本文件。

## 一键启动（Windows）

双击 `run-local.bat`：自动启动 PostgreSQL / MinIO / Redis 容器，构建判题节点镜像并启动 1 个本地节点，执行数据库迁移与演示账号引导，随后弹出后端（8000）与前端（5173）窗口。

## 本地运行（不用 Docker）

依赖：Python 3.12+、Node 20+、本地 PostgreSQL / Redis / MinIO。

```bash
# 后端（判题 gRPC 网关 :50051 与维护循环随应用启动）
cd src/backend && pip install -r requirements.txt && alembic upgrade head && python run.py

# 前端
cd src/frontend && npm install && npm run dev
```

- 后端 `http://localhost:8000`（API `/api/v1`）；前端 `http://localhost:5173`（vite 代理 `/api` 到 8000）
- `vite.config.ts` 是唯一生效的 vite 配置，`vue-tsc -b` 产物已重定向到 `node_modules/.vite-config/`

## Docker 运行

```bash
# 生产（后端 + 前端 + 基础设施）
# ⚠️ --env-file 必须加：compose 的 ${VAR} 插值只认 compose 文件同目录的 .env
docker compose --env-file .env -f docker/docker-compose.yml up -d --build

# 判题节点镜像
docker build -t pigeonoj/judge-node src/judge

# 判题节点容器（改 SERVER_ADDRESS 为后端公网地址；.env.node.example → .env.node）
docker compose --env-file .env.node --project-directory . -f docker/docker-compose-node.yml up -d --build
```

### 最低资源要求

- compose 顶层 `name: pigeonoj`，卷名 `pigeonoj_pgdata` 等
- 各服务 `mem_limit`：db 384m / redis 128m / minio 384m / backend 512m / frontend 64m / 节点 1g
- 前端构建（vue-tsc + vite）建议 ≥ 2GB 内存 + ≥ 1GB swap；小内存注入：`docker compose build --build-arg NODE_OPTIONS=--max-old-space-size=1536 frontend`
- Docker Hub 不可达时配置 `/etc/docker/daemon.json` 镜像加速器

### 判题节点与沙箱

- **后端进程不执行任何用户代码**；代码执行只发生在 `pigeonoj/judge-node` 容器内；后端仅提供 gRPC 网关（`:50051`）
- 组网三选一：同机（`SERVER_ADDRESS=backend:50051`）、单域名路径复用 443（边缘 nginx 按 `/pigeonoj.judge.v1.JudgeGateway/` `grpc_pass`）、直连（改绑 `"50051:50051"`）
- 节点需要 `privileged: true`（nsjail 嵌套 namespace）；出站连接网关，无入站端口
- `/cache` 上限默认 `JUDGE_CACHE_MAX_MB=512`，节点定时回收超限按 LRU（判题中目录保护）
- 支持入口与执行规范见 `docs/contracts/judge.md`

### 部署拓扑

| 形态 | 适用 | 端口 |
| --- | --- | --- |
| 边缘代理（推荐生产） | 宿主机 nginx / Caddy | 保持默认（前端 8080、网关回环 50051） |
| 无反代裸服务器 | 内网 / 快速验证 | 前端改绑 `"80:80"`、网关 `"50051:50051"` |

部署在已有 Nginx 后：保持前端 `8080:80` 不变，由宿主机反代。

### 真实客户端 IP（X-Forwarded-For）

反代场景下后端 uvicorn 以 `--proxy-headers --forwarded-allow-ips="*"` 启动（仅 compose 内网可达，容器网络不暴露公网）；
应用层从 `X-Forwarded-For` 取**左起第一个公网地址**为客户端 IP（伪造值只能污染私有段左侧），全私有段取最左合法值，再回退
`X-Real-IP`、直连 peer（`app/utils/request_meta.py` 的 `resolve_client_ip`，中间件与 auth 路由统一走此函数）。
每条响应回传 `X-Request-Id`，与 `request_logs.request_id` 一一对应，客户端反馈问题可据此检索日志。

## 后端配置

配置主文件 `src/backend/backend.toml`，`src/backend/app/settings/config.py` 只负责加载。优先级：进程环境变量 → `.env` → `backend.toml`。

TOML 分段拍平为下划线字段（`[minio] endpoint` → `MINIO_ENDPOINT`）；`.env` 仅放需要覆盖的项。

## 环境变量

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ENVIRONMENT` | 运行环境 | `development` / `production` |
| `SECRET_KEY` | 会话 / 加密主密钥（生产必改） | 随机长字符串 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `POSTGRES_USER/PASSWORD/DB` | PostgreSQL（仅 docker compose 基础设施） | `pigeonoj` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 后端连接池常驻 / 突发溢出上限（总连接 = 两者之和，需匹配 PG `max_connections` × 副本数） | `20` / `30` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | MinIO 端点 | `localhost:9000` |
| `MINIO_ACCESS_KEY/SECRET_KEY` | MinIO 密钥 | `pigeonoj` |
| `MINIO_BUCKET` | MinIO 存储桶 | `pigeonoj` |
| `MINIO_SECURE` | HTTPS（生产置 true） | `false` |
| `JUDGE_GATEWAY_TOKENS` | 节点注册令牌（逗号分隔）；为空网关不启动 | — |
| `JUDGE_GRPC_HOST/PORT` | 网关监听地址/端口 | `0.0.0.0` / `50051` |
| `TEST_DATABASE_URL` | 测试库连接串 | `postgresql+asyncpg://...@localhost:5432/pigeonoj_test` |
| `BOOTSTRAP_ADMIN_EMAIL/PASSWORD` | 初始管理员引导 | `admin@example.com` |

> CORS 来源在 backend.toml `[cors] origins`；环境变量覆盖时为 JSON 数组。
> 判题节点自身配置见 `.env.node.example`，不属于后端环境变量。
> AI 能力暂缓实现，配置域不引入。

## Redis 约定

### Key 清单

| Key | 说明 | TTL |
| --- | --- | --- |
| `team:invite:<token>` | 团队邀请链接 → {team_id} | 链接有效期 |
| `verify_invite:{token}` | 验题邀请链接 → {"problem_id": "..."} | 有效期（发起时指定小时数） |
| `session:<token>` | 会话热点缓存 | 会话有效期 |
| `email:code:<email>:<purpose>` | 邮箱验证码 + 错误计数 | 验证码有效期 |
| `email:resend:<email>:<purpose>` | 验证码重发间隔计数 | 重发间隔 |
| `rank:contest:<id>` | 榜单读缓存（权威在 `contest_rankings`） | 进行中 20s / 封榜 60s / 完赛已解冻 永久 |
| `rank:contest:<id>:lock` | 榜单缓存重建互斥锁（防击穿，未抢到方等待重读后兜底回源） | 10s |
| `login:fail:<email>` | 登录失败计数（窗口内超次触发临时锁定） | 15 分钟 |
| `login:lock:<email>` | 登录临时锁定标记（到期自动恢复，不改动账号状态） | 15 分钟 |
| `sandbox:node:<id>` | 判题节点运行时状态 | 心跳周期（过期视为离线） |
| `judge:cooldown:<user_id>:<problem_id>` | 提交冷却 | 冷却时长 |
| `judge:selftest:<user_id>:<problem_id>` | 用户自测冷却 | 复用冷却配置 |
| `judge:requeue:<submission_id>` | 维护循环重派互斥锁 | 重派窗口 |
| `upload:rate:<kind>:<user_id>` | 文件上传固定窗口计数（kind = avatar / image / site_logo） | 窗口（1 小时） |

### 缓存一致性

- 会话、邀请链接、判题节点状态为 Redis 唯一事实来源，不落库
- 榜单以数据库 `contest_rankings` 为权威，Redis 仅作读缓存；写路径（判题回写、自动封榜、手动解冻）主动失效，
  且判题回写与解冻在 **DB commit 后**补删一次（消除「先删缓存后提交」窗口内并发读回填旧榜单）；
  Redis 异常时读写全部降级直查数据库，分级 TTL 兜底最终一致（进行中 TTL 取大于前端 15s 轮询间隔，令轮询命中缓存）
- 全局判题并发上限由网关注册表在内存统计（节点 in-flight 之和），不占 Redis

## 后台调度机制

均以进程内 asyncio 循环实现（与网关同生命周期），不引入 Celery / 外部队列。

| 机制 | 说明 | 现状 |
| --- | --- | --- |
| gRPC 网关派发 | 按任务数最少优先选节点（跳过上行消息超时的僵死节点），原子认领后沿双向流推送；无在线节点保持 pending | 已实现 |
| 网关维护循环 | 每 30s 扫描超时提交（复位 pending 重派、断线节点 in-flight 回收） | 已实现 |
| 节点心跳桥接 | 上行 Heartbeat → 写 Redis `sandbox:node:<id>`；单条消息处理失败（Redis/DB 瞬断）只记日志不终止流 | 已实现 |
| 节点判活护栏 | 派发与并发统计跳过超过 max(2×心跳间隔, 心跳 TTL) 未收到上行消息的节点；上行泵退出经 watchdog 触发连接清理（注销 / 置错 / 删心跳 / 离线日志） | 已实现 |
| 比赛状态推进 | 封榜 / 解封 / 结束重算（`contest_transition`） | 随 contests 模块实现 |

## MinIO 存储规范

| 对象 key | 说明 |
| --- | --- |
| `problems/{problem_id}/cases/{case_id}/input` | 判题测试点输入 |
| `problems/{problem_id}/cases/{case_id}/output` | 判题测试点期望输出 |
| `submissions/{submission_id}/cases/{case_id}/output` | 提交运行输出 |
| `users/{user_id}/avatar` | 用户头像 |
| `teams/{team_id}/avatar` | 团队头像 |
| `site/logo/{uuid}` | 站点 Logo（系统配置 `site.logo`，经 `POST /files/upload/site-logo` 上传） |

上传方式：经 `POST /files/upload` 后端校验后转存 MinIO，对象 key 由服务端生成并回填 ossId。**判题节点不访问 MinIO**：经网关按 `data_version` 流式拉取到节点本地缓存。测试点不向前端签发预签名 URL。

## 可观测性

- `request_logs`：全量请求（含 `request_id` 追踪）；沙箱执行日志作为子记录归入 `extra`
- `login_logs`：登录 / 登出 / 注册 / 换绑
- `exception_levels`：level（`error` / `warning` / `fatal`）+ traceback + request_id

## 测试

```bash
npm run lint:check       # 前端 ESLint
pip install -r requirements-dev.txt   # 测试依赖（pytest / pytest-asyncio / httpx，均在 src/backend 下执行）
pytest                   # 后端单元 + 集成测试
npm test                 # 前端 Vitest
```

### 前端工程化

- 格式化由 Prettier 负责，ESLint 关闭格式类规则，双工具不打架
- Vitest jsdom 环境（dict.ts / http.ts 依赖 localStorage 与 DOMPurify）
- 测试与被测文件同目录，命名 `*.spec.ts`
- 模板内联事件禁止多条语句（Prettier 折行后生成非法表达式）

### 后端测试

- `src/backend/tests/conftest.py` 默认连接 `pigeonoj_test` 库（自动 `drop_all` / `create_all`）+ Redis db 15
- ⚠️ 不要在跑 pytest 时把 `DATABASE_URL` 指向开发库；可用 `TEST_DATABASE_URL` 覆盖
- pytest async 测试共享会话级事件循环

### 开发辅助脚本（`src/backend/scripts/`）

```bash
python -m scripts.bootstrap_admin         # 管理员引导
python -m scripts.bootstrap_demo_users   # 引导演示账号
python -m scripts.smoke_test             # 端到端冒烟
python scripts/verify_db.py              # 校验迁移与种子数据
python scripts/check_import_rules.py     # 分层导入规则机械检查
```

### 测试策略

- 单元测试覆盖 Service；集成测试覆盖 Route → Service → Repository
- 端点覆盖：成功 + 每种错误码 + 边界值
- 判题 / 沙箱相关测试无沙箱环境时 skip 或 mock

> 邮箱验证码发信：SMTP host 为空（默认）时开发/测试环境打印验证码到后端日志；生产环境返回 `5001`（邮件服务未配置），避免静默失败。

## 生产检查清单

- [ ] 环境变量已配置且无默认弱值
- [ ] `JUDGE_GATEWAY_TOKENS` 已设置
- [ ] `CORS_ORIGINS` 已设为实际域名
- [ ] 数据库迁移已执行
- [ ] 初始管理员已创建（勿用演示账号当生产管理员）
- [ ] HTTPS 已启用
- [ ] `.env` 未提交版本控制
- [ ] MinIO bucket 已创建且后端具备读写权限
- [ ] 沙箱节点已注册且健康

## 禁止事项

- 不硬编码 URL、端口、密钥
- 不在 Dockerfile 中写死环境变量值
- 不把 `.env` 打包进镜像
- 生产环境不暴露 `debug` 级别日志
- 测试点对象不向前端暴露预签名 URL
