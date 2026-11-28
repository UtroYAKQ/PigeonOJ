# 运行、测试与运维

> 如何运行、测试、部署；基础设施约定（Redis、调度、对象存储）。涉及配置或发布变更时读本文件。
> 沙箱执行细节见 `contracts.md` §10.11，此处只讲部署约束。

## 1. 本地运行

### 1.1 一键启动（Windows）

双击 `run-local.bat`：自动启动 PostgreSQL / MinIO / Redis 容器，检测并安装缺失依赖（`pip install -r requirements.txt` / `npm install`），判题节点镜像缺失时才构建（已有则复用），在独立窗口启动 1 个本地节点（`compose up`，日志可见，无需手工 `--env-file`），执行数据库迁移与演示账号引导，随后弹出后端与前端（5173）窗口。

后端端口取配置链（进程环境变量 > `.env` 的 `SERVER_PORT` > `backend.toml` `[server] port`，默认 8000），脚本据此导出供 vite 代理联动。

**启动前自清理**：`run.py` 以 uvicorn `--reload` 运行，直接关闭窗口时 worker 子进程可能成为孤儿继续占用端口。脚本在启动前后端前先按端口（`SERVER_PORT` / 5173）清理 LISTENING 残留进程，**重复运行脚本即等价于重启**。

> ⚠️ `run-local.bat` 当前 `cd src\frontend`（旧工程），而 `docker/docker-compose.yml` 已切 `src/frontend-next`。用一键脚本做前端开发需先把脚本路径改为 `src\frontend-next`。

**停止服务**：双击 `stop-local.bat`——按端口结束后端与前端、`docker compose down` 判题节点容器（镜像保留）。关窗口可能留下孤儿 reload worker，不是可靠停止手段。

### 1.2 手动运行

依赖：Python 3.12+、Node 20+、本地 PostgreSQL / Redis / MinIO。

**后端虚拟环境（必须）**：统一使用**仓库根目录 `.venv`**（已入 `.gitignore`）。不存在就创建，存在就直接用；所有后端命令（运行 / alembic / pytest / 脚本）一律走该解释器，**不装进全局 Python**。

```bash
# 无 .venv 时
python -m venv .venv
.venv/Scripts/python -m pip install -r src/backend/requirements.txt -r src/backend/requirements-dev.txt

# 有 .venv 时（Git Bash）
source .venv/Scripts/activate
# 或免激活直接调用
.venv/Scripts/python src/backend/scripts/check_import_rules.py
```

```bash
# 后端（判题 gRPC 网关 :50051 与维护循环随应用启动）
cd src/backend && ../../.venv/Scripts/python -m alembic upgrade head && ../../.venv/Scripts/python run.py

# 前端
cd src/frontend-next && npm install && npm run dev
```

- 后端 `http://localhost:8000`（API `/api/v1`，端口可经 `SERVER_PORT` 覆盖）
- 前端 `http://localhost:5173`（vite 代理 `/api` 到后端，代理目标读 `SERVER_PORT`，默认 8000）
- `vue-tsc -b` 产物重定向到 `node_modules/.vite-config/`

## 2. Docker 部署

```bash
# 生产（后端 + 前端 + 基础设施）
# ⚠️ --env-file 必须加：compose 的 ${VAR} 插值只认 compose 文件同目录的 .env
docker compose --env-file .env -f docker/docker-compose.yml up -d --build

# 判题节点镜像
docker build -t pigeonoj/judge-node src/judge

# 判题节点容器（.env.node.example → .env.node，填 SERVER_HOST + SERVER_GRPC_PORT 或整体 SERVER_ADDRESS）
docker compose --env-file .env.node --project-directory . -f docker/docker-compose-node.yml up -d --build
```

### 最低资源要求

- compose 顶层 `name: pigeonoj`，卷名 `pigeonoj_pgdata` 等
- 各服务 `mem_limit`：db 384m / redis 128m / minio 384m / backend 512m / frontend 64m / 节点 `JUDGE_NODE_MEM_LIMIT`（默认 4g）
- 前端构建（vue-tsc + vite）建议 ≥2GB 内存 + ≥1GB swap；小内存注入：`docker compose build --build-arg NODE_OPTIONS=--max-old-space-size=1536 frontend`
- Docker Hub 不可达时配置 `/etc/docker/daemon.json` 镜像加速器

### 部署拓扑

| 形态 | 适用 | 端口 |
| --- | --- | --- |
| 边缘代理（推荐生产） | 宿主机 nginx / Caddy | 前端 8080、网关回环 50051 |
| 无反代裸服务器 | 内网 / 快速验证 | 前端改绑 `"80:80"`、网关 `"50051:50051"` |

### 真实客户端 IP

反代场景下 uvicorn 以 `--proxy-headers --forwarded-allow-ips="*"` 启动（仅 compose 内网可达）。应用层从 `X-Forwarded-For` 取**左起第一个公网地址**（伪造值只能污染私有段左侧），全私有段取最左合法值，再回退 `X-Real-IP`、直连 peer（`app/utils/request_meta.py` 的 `resolve_client_ip`，中间件与 auth 路由统一走此函数）。

## 3. 判题节点

- **后端进程不执行任何用户代码**；执行只发生在 `pigeonoj/judge-node` 容器内，后端仅提供 gRPC 网关（`:50051`）
- 容器内存上限 `JUDGE_NODE_MEM_LIMIT`（默认 4g）须 ≥ `CAPACITY × CASE_PARALLEL × 单题内存` 并留编译余量，否则 cgroup v2 嵌套下并发 box 会触发容器级 OOM（可能连 daemon 一起杀）
- 组网三选一：同机（`SERVER_HOST=backend` + `SERVER_GRPC_PORT=50051`）、单域名路径复用 443（边缘 nginx 按 `/pigeonoj.judge.v1.JudgeGateway/` `grpc_pass`）、直连（改绑 `"50051:50051"`）；节点侧 `SERVER_GRPC_PORT` 须与后端 `JUDGE_GRPC_PORT` 一致（也可整体用 `SERVER_ADDRESS` 覆盖）
- **需要 `privileged: true` 且 `cgroup: host`**（= `--cgroupns=host`）：isolate 要在 `/sys/fs/cgroup/isolate` 下建 box 子组并写 `memory.max`。私有 cgroup namespace 下容器根 cgroup 被 init 进程占用，写 `subtree_control` 报 EBUSY，isolate 随即报 `Cannot set .../cgroup.procs: Operation not supported`。宿主机需 cgroup v2（`/sys/fs/cgroup/cgroup.controllers` 存在），否则节点启动即失败而非降级。入口 `docker-entrypoint.sh` 建 `cg_root` 并在父层级与 isolate 根上委派 `memory` / `pids`。判题 gRPC 仍只出站
- 可选本机管理页（默认 `127.0.0.1:18080`，容器内 `0.0.0.0` 但 compose 只映射宿主机回环）：改网关地址 / 令牌、TCP 探测、容量与并行度；`JUDGE_ADMIN_PORT=0` 关闭；token 掩码返回；写入 `/cache/node.runtime.toml`（挂载卷），**优先于** compose 环境变量，容器重建后保留
- 镜像多阶段构建：`ISOLATE_VERSION` 编译 isolate 后丢弃 build-essential / git / libcap-dev；运行时仅保留 g++ / JDK / Python / libcap2
- 节点参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `JUDGE_NODE_CAPACITY` | — | 同时受理作业数 |
| `JUDGE_CASE_PARALLEL` | 4 | IOI / 练习 / 验题同作业并行测试点数；ACM `stop_on_failure` 仍串行 |
| `JUDGE_ISOLATE_BOX_POOL` | 10 | 启动时预建 box 池（最多 8 路并行 `--init`），热路径只跑 `--run`；建议 ≥ `CAPACITY × (CASE_PARALLEL + 1)` |
| `JUDGE_ISOLATE_BOX_ID_BASE` | — | 同机跑多节点进程时错开 box-id 区间 |
| `JUDGE_ISOLATE_ACQUIRE_TIMEOUT` | 60s | 等不到空闲 box 即报 `system_error`，避免线程挂到网关 5min 判死 |
| `JUDGE_CACHE_MAX_MB` | 512 | `/cache` 上限，定时按 LRU 回收（判题中目录保护） |

- SPJ 二进制缓存：同一 `problem_id + data_version` 的 `spj.cpp` 只编译一次，产物 `spj.bin` 落在题目 `/cache` 目录并随 LRU 回收；`spj.cpp` mtime 更新会自动失效重编

- 并发度与 CPU：`CAPACITY × CASE_PARALLEL` 不应超过容器可用 CPU 核数；超卖会让程序争抢 CPU、推高 wall 时间，可能把 AC 误判为 TLE（启动校验并告警，不阻断）
- gRPC 收发上限 128MB（网关与节点 channel 对齐）；测试点 ≤8MB、默认输出 5MB×N——默认 4MB 会卡死 Connect / FetchProblemData

## 4. 后端配置

配置主文件 `src/backend/backend.toml`，`app/settings/config.py` 只负责加载。优先级：进程环境变量 → `.env` → `backend.toml`。TOML 分段拍平为下划线字段（`[minio] endpoint` → `MINIO_ENDPOINT`）；`.env` 仅放需要覆盖的项。

### 环境变量

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ENVIRONMENT` | 运行环境 | `development` / `production` |
| `SECRET_KEY` | 会话 / 加密主密钥（生产必改） | 随机长字符串 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `SERVER_PORT` | 后端 HTTP 端口（本地；生产容器 CMD 固定 8000） | `8000` |
| `POSTGRES_USER/PASSWORD/DB` | PostgreSQL（仅 compose 基础设施） | `pigeonoj` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 连接池常驻 / 溢出上限（总连接 = 两者之和，需匹配 PG `max_connections` × 副本数） | `20` / `30` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | MinIO 端点 | `localhost:9000` |
| `MINIO_ACCESS_KEY/SECRET_KEY` | MinIO 密钥 | `pigeonoj` |
| `MINIO_BUCKET` | 存储桶 | `pigeonoj` |
| `MINIO_SECURE` | HTTPS（生产置 true） | `false` |
| `JUDGE_GATEWAY_TOKENS` | 节点注册令牌（逗号分隔）；为空网关不启动 | — |
| `JUDGE_GRPC_HOST/PORT` | 网关监听地址 / 端口 | `0.0.0.0` / `50051` |
| `TEST_DATABASE_URL` | 测试库连接串 | `postgresql+asyncpg://...@localhost:5432/pigeonoj_test` |
| `BOOTSTRAP_ADMIN_EMAIL/PASSWORD` | 初始管理员引导 | `admin@example.com` |

> CORS 来源在 `backend.toml` `[cors] origins`；环境变量覆盖时为 JSON 数组。
> 判题节点自身配置见 `.env.node.example`，不属于后端环境变量。

## 5. Redis 约定

### Key 清单

| Key | 说明 | TTL |
| --- | --- | --- |
| `team:invite:<token>` | 团队邀请链接 → {team_id} | 链接有效期 |
| `verify_invite:{token}` | 验题邀请链接 → {"problem_id": "..."} | 有效期（发起时指定小时数） |
| `session:<token>` | 会话热点缓存 | 会话有效期 |
| `session:active:<token>` | 会话活跃节流标记（到期回写 `last_active_at`；「在线中」依据） | 5 分钟 |
| `email:code:<email>:<purpose>` | 邮箱验证码 + 错误计数 | 验证码有效期 |
| `email:resend:<email>:<purpose>` | 验证码重发间隔计数 | 重发间隔 |
| `rank:contest:<id>` | 榜单读缓存（权威在 `contest_rankings`） | 进行中 20s / 封榜 60s / 完赛已解冻 永久 |
| `rank:contest:<id>:lock` | 榜单缓存重建互斥锁（防击穿） | 10s |
| `login:fail:<email>` | 登录失败计数（超次落库短时冻结） | 15 分钟 |
| `sandbox:node:<id>` | 判题节点运行时状态 | 心跳周期（过期视为离线） |
| `judge:cooldown:<user_id>:<problem_id>` | 提交冷却 | 冷却时长 |
| `judge:selftest:<user_id>:<problem_id>` | 用户自测冷却 | 复用冷却配置 |
| `judge:requeue:<submission_id>` | 维护循环重派互斥锁（失败 5s / 成功升级 300s 在途保护） | 5s / 300s |
| `judge:attempts:<submission_id>` | 断线 / judging 超时回收次数；满 3 次转 system_error | 1 小时 |
| `upload:rate:<kind>:<user_id>` | 上传固定窗口计数（kind = avatar / image / site_logo） | 1 小时 |

### 缓存一致性

- 会话、邀请链接、判题节点状态为 Redis 唯一事实来源，不落库
- 榜单以 `contest_rankings` 为权威，Redis 仅读缓存；写路径（判题回写、自动封榜、手动解冻）主动失效，且判题回写与解冻在 **DB commit 后**补删一次（消除「先删缓存后提交」窗口内并发读回填旧榜单）；Redis 异常时读写降级直查数据库，分级 TTL 兜底最终一致（进行中 TTL 大于前端 15s 轮询间隔，令轮询命中缓存）
- 全局判题并发上限由网关注册表在内存统计（节点 in-flight 之和），不占 Redis

## 6. 后台调度

均以进程内 asyncio 循环实现（与网关同生命周期），不引入 Celery。

| 机制 | 说明 |
| --- | --- |
| gRPC 网关派发 | 按任务数最少优先选节点（跳过上行消息超时的僵死节点），原子认领后沿双向流推送；无在线节点保持 pending |
| 网关维护循环 | pending 不设滞留门槛（有空位即派）；节点容量释放 / 注册 / 重连即踢醒巡检，30s 周期兜底；judging 超时（5min）复位重派、断线节点 in-flight 回收 |
| 节点心跳桥接 | 上行 Heartbeat → 写 Redis `sandbox:node:<id>`；单条消息处理失败只记日志不终止流 |
| 节点判活护栏 | 派发与并发统计跳过超过 max(2×心跳间隔, 心跳 TTL) 无上行消息的节点；上行泵退出经 watchdog 触发连接清理 |
| 比赛状态推进 | `contest_transition`：开赛 / 自动封榜 / 结束重算 |

## 7. MinIO 存储规范

| 对象 key | 说明 |
| --- | --- |
| `problems/{problem_id}/cases/{case_id}/input` | 测试点输入 |
| `problems/{problem_id}/cases/{case_id}/output` | 测试点期望输出 |
| `problems/{problem_id}/spj/{uuid}/code` | SPJ 特判程序源码 |
| `submissions/{submission_id}/cases/{case_id}/output` | 提交运行输出 |
| `users/{user_id}/avatar` | 用户头像 |
| `users/{user_id}/avatar/{uuid}@w{width}.webp` | 头像缩略图（首次生成，width ∈ 96/192/384/640/960/1280） |
| `users/{user_id}/images/{uuid}@w{width}.webp` | 公共图片缩略图（题面插图等） |
| `site/logo/{uuid}` | 站点 Logo |

上传经 `POST /files/upload` 校验后转存 MinIO，key 由服务端生成。**判题节点不访问 MinIO**：经网关按 `data_version` 流式拉取到本地缓存。测试点不向前端签发预签名 URL。

## 8. 可观测性

- `request_logs`：全量请求（含 `request_id` 追踪）；沙箱执行日志作为子记录归入 `extra`
- `login_logs`：登录 / 登出 / 注册 / 换绑
- `exception_logs`：level（`error` / `warning` / `fatal`）+ traceback + request_id

## 9. 测试

```bash
# 后端
.venv/Scripts/python -m pip install -r src/backend/requirements-dev.txt   # 首次或依赖变更后
cd src/backend && ../../.venv/Scripts/python -m pytest
../../.venv/Scripts/python scripts/check_import_rules.py                  # 分层导入规则

# 前端
cd src/frontend-next && npm run lint:check && npm test && npm run build

# 判题节点（无需 isolate）
cd src/judge/node && pytest

# 判题节点集成（需真机 isolate，节点容器内装 requirements-dev.txt 后）
ISOLATE_INTEGRATION=1 pytest test_isolate_integration.py test_daemon_e2e.py
```

### 后端测试约定

- `tests/conftest.py` 默认连 `pigeonoj_test` 库（自动 `drop_all` / `create_all`）+ Redis db 15
- ⚠️ 不要在跑 pytest 时把 `DATABASE_URL` 指向开发库；可用 `TEST_DATABASE_URL` 覆盖
- pytest async 测试共享会话级事件循环

### 判题节点测试覆盖

- 单元（无需 isolate）：SPJ 判定映射、指标采集、执行器 argv 与 meta 状态映射、box 池借还重建、管理页解析与配置写回
- 集成（真机 isolate）：三语言 AC/WA/CE/TLE/MLE/OLE/RE、SPJ 四种结局、沙箱边界（作业目录只读、`/tmp` 可写、box 不跨运行泄漏、无网络）、并发 box 隔离、连跑 60 次无泄漏；`test_daemon_e2e.py` 覆盖注册 → 派发 → 拉取数据 → 判题 → 回传全链路

### 测试策略

- 单元测试覆盖 Service；集成测试覆盖 Route → Service → Repository
- 端点覆盖：成功 + 每种错误码 + 边界值
- 判题 / 沙箱相关测试无沙箱环境时 skip 或 mock

### 前端工程化

- 格式化由 Prettier 负责，ESLint 关闭格式类规则
- Vitest jsdom 环境（dict.ts / http.ts 依赖 localStorage 与 DOMPurify）；测试与被测文件同目录，命名 `*.spec.ts`
- 模板内联事件禁止多条语句（Prettier 折行后生成非法表达式）

### 开发辅助脚本（`src/backend/scripts/`）

在 `src/backend` 下用根目录 `.venv` 解释器执行：

```bash
python -m scripts.bootstrap_admin         # 管理员引导
python -m scripts.bootstrap_demo_users    # 演示账号引导
python -m scripts.smoke_test              # 端到端冒烟
python scripts/verify_db.py               # 校验迁移与种子数据
python scripts/check_import_rules.py      # 分层导入规则机械检查
python -m scripts.import_fps_problems <xml|zip|URL> ...   # FPS 题库导入
python -m scripts.crawl_loj --begin 100 --end 199         # LibreOJ 题目爬取
```

> 详细用法见 `src/backend/scripts/README_import_fps_problems.md` 与 `README_crawl_loj.md`。

## 10. 生产检查清单

- [ ] 环境变量已配置且无默认弱值
- [ ] `JUDGE_GATEWAY_TOKENS` 已设置
- [ ] `CORS_ORIGINS` 已设为实际域名
- [ ] 数据库迁移已执行
- [ ] 初始管理员已创建（勿用演示账号当生产管理员）
- [ ] HTTPS 已启用
- [ ] `.env` 未提交版本控制
- [ ] MinIO bucket 已创建且后端具备读写权限
- [ ] 沙箱节点已注册且健康
- [ ] SMTP 已配置（否则生产环境验证码发信返回 5001）

## 11. 禁止事项

- 不硬编码 URL、端口、密钥
- 不在 Dockerfile 中写死环境变量值
- 不把 `.env` 打包进镜像
- 生产环境不暴露 `debug` 级别日志
- 测试点对象不向前端暴露预签名 URL
- 不用全局 Python 跑后端命令（必须用根目录 `.venv`）
