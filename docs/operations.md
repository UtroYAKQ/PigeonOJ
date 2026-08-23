# 运行与运维（测试 · 部署 · 环境变量）

> 如何运行、测试与部署本项目，以及所有环境变量。涉及配置或发布变更时先读本文件。

## 一键启动（Windows）

双击仓库根目录的 `run-local.bat`：自动启动 PostgreSQL / MinIO / Redis 容器（本地镜像，不拉取），构建并冒烟验证 nsjail 沙箱，执行数据库迁移与演示账号引导，随后弹出两个窗口分别运行后端（8000）与前端（5173，真实 API 模式）。

## 本地运行（不用 Docker）

依赖：Python 3.12+、Node 20+、本地 PostgreSQL / Redis / MinIO。

```bash
# 后端
cd src/backend && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload

# Celery worker（含 beat）
cd src/backend && celery -A app.worker.celery_app worker -l info --beat

# 前端
cd src/frontend && npm install && npm run dev
```

- 后端：`http://localhost:8000`（API 前缀 `/api/v1`）
- 前端：`http://localhost:5173`（dev 模式通过 vite 代理把 `/api` 转发到 `localhost:8000`，前端相对路径 `/api/v1` 即可直连，无需处理 CORS）
- 注意：`vite.config.ts` 是唯一生效的 vite 配置 —— `vue-tsc -b` 的编译产物已重定向到 `node_modules/.vite-config/`，不会生成根目录 `vite.config.js` 抢占加载（vite 优先加载 `.js` 配置）

## Docker 运行

```bash
# 开发（PostgreSQL + Redis + MinIO + 后端热重载；前端本地 npm run dev）
docker compose -f docker/docker-compose-dev.yml up --build

# 生产（后端 + Celery + 前端 + 基础设施）
docker compose -f docker/docker-compose.yml up -d

# 构建本地 nsjail 沙箱基础镜像（判题节点镜像的底座，也用于冒烟验证）
docker build -t sandbox:local src/judge/sandbox

# 构建并启动判题节点容器（在另一台服务器上部署时改 SERVER_ADDRESS 为后端公网地址）
SERVER_ADDRESS=host.docker.internal:50051 SERVER_TOKEN=dev-token \
docker compose -f src/judge/docker-compose-node.yml up -d --build

# 冒烟：沙箱镜像内跑一次示例（输入通过 stdin 传入）
Get-Content .\src\judge\sandbox\examples\input.txt | docker compose -f docker/docker-compose-sandbox.yml run --rm -T sandbox python3.12 /sandbox/examples/Main.py
```

### 判题节点与沙箱说明

- **后端进程不执行任何用户代码**。代码执行只发生在 `pigeonoj/judge-node` 容器内；
  后端仅提供 gRPC 网关（`:50051`）做注册认证、负载均衡派发与结果落库。
- 节点镜像 = 沙箱基础镜像（Ubuntu 24.04 + 阿里云 APT 源 + nsjail 3.4 + Python/C++/Java 工具链）+ grpcio + 守护进程
  （`src/judge/Dockerfile`）。基础镜像单独构建为 `sandbox:local` 供冒烟使用。
- 节点固定挂载两个宿主机目录：工作区 → 容器 `/sandbox`（每作业子目录自动创建/清理）、
  数据缓存 → 容器 `/cache`（按题目 data_version 复用）。绝不能配置为宿主机根目录、用户代码目录或 Docker socket。
- 节点需要 `privileged: true`（nsjail 嵌套 namespace）并**只做出站连接**后端网关；不开放任何入站端口。
- 配置来源：`src/judge/node/node.toml`，环境变量 `SERVER_ADDRESS / SERVER_TOKEN /
  JUDGE_NODE_ID / JUDGE_NODE_NAME / JUDGE_NODE_CAPACITY` 可覆盖。
- 运行器为 `sandbox/run-in-nsjail.sh` 同源的执行语义：只允许源码和输入位于 `/sandbox`，
  Python/C++/Java 编译与运行均在 nsjail 内完成；C++/Java 一次提交只编译一次，逐测试点独立运行。
- 正式判题限制由后端按 `sandbox_configs` 比例换算后随作业下发；不要把测试点期望输出或宿主机路径传给前端。

支持入口与执行规范见 [docs/contracts/judge.md](contracts/judge.md)。

## 环境变量

所有变量列在 `.env.example`。本地使用：`cp .env.example .env`。

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ENVIRONMENT` | 运行环境 | `development` / `production` |
| `SECRET_KEY` | 会话 / 加密主密钥（生产必改） | 随机长字符串 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `POSTGRES_USER` | PostgreSQL 用户 | `pigeonoj` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | `pigeonoj` |
| `POSTGRES_DB` | PostgreSQL 库名 | `pigeonoj` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery Broker | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery 结果后端 | `redis://localhost:6379/2` |
| `MINIO_ENDPOINT` | MinIO 端点 | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥 | `pigeonoj` |
| `MINIO_SECRET_KEY` | MinIO 密钥 | `pigeonoj-minio-secret` |
| `MINIO_BUCKET` | MinIO 存储桶 | `pigeonoj` |
| `MINIO_SECURE` | 是否启用 HTTPS（生产置 true） | `false` |
| `MINIO_BUCKET` | MinIO 存储桶，文件 Service 启动时使用 | `pigeonoj` |
| `VITE_API_BASE_URL` | 前端 API 基址 | `http://localhost:8000/api/v1` |
| `JUDGE_GATEWAY_TOKENS` | 判题节点注册令牌（逗号分隔多个）；为空则网关不启动。节点 node.toml 的 server.token 需匹配其一 | 空 |
| `JUDGE_GRPC_HOST` | 判题网关 gRPC 监听地址 | `0.0.0.0` |
| `JUDGE_GRPC_PORT` | 判题网关 gRPC 监听端口 | `50051` |
| `SANDBOX_IMAGE` | 本地 nsjail 沙箱镜像名（compose 构建产物标签，判题节点镜像的底座） | `sandbox:local` |
| `SANDBOX_WORKSPACE_DIR` | 宿主机受控工作目录，挂载到容器 `/sandbox` | `../.docker-data/sandbox-work` |
| `SANDBOX_EXAMPLES_DIR` | 本地示例目录，只读挂载到容器 `/sandbox/examples` | `../src/judge/sandbox/examples` |

> 判题节点自身的配置（SERVER_ADDRESS / SERVER_TOKEN / JUDGE_NODE_ID / JUDGE_NODE_NAME /
> JUDGE_NODE_CAPACITY）来自节点侧 `src/judge/node/node.toml`，环境变量可覆盖；
> 不属于后端环境变量。

> 大模型配置（各 AI 能力所用模型、API Key）在 `system_configs` / `model_configs` 中管理（Key 加密存储），不通过环境变量注入；`.env.example` 仅提供提供方级兜底 Key 的可选项。当前阶段 AI 模块（含模型配置 / Token 用量）暂缓实现。

## 测试

```bash
pytest                  # 后端单元 + 集成测试（pytest + pytest-asyncio）
npm test                # 前端单元测试（Vitest）
```

后端集成测试需要本地 PostgreSQL / Redis（`src/backend/tests/conftest.py`）：

- 默认连接 `pigeonoj_test` 库（自动 `drop_all` / `create_all` 重建表 + 种子角色/配置）与 Redis **db 15**
- ⚠️ **不要在跑 pytest 时把 `DATABASE_URL` 指向开发库** —— 测试会重建表结构；可用 `TEST_DATABASE_URL` 覆盖测试库
- pytest 配置（`pytest.ini`）：async 测试 / fixture 共享会话级事件循环（模块级异步引擎的连接池只绑定一个循环）

开发辅助脚本（`src/backend/scripts/`）：

```bash
python -m scripts.bootstrap_demo_users   # 引导演示账号 admin/tutor/user（开发期联调用）
python -m scripts.smoke_test             # 端到端冒烟（httpx ASGI 全链路）
python scripts/verify_db.py              # 校验迁移与种子数据
```

策略：

- 单元测试覆盖 Service 逻辑；集成测试覆盖 Route → Service → Repository 完整链路
- 每个端点覆盖：成功场景 + 每种错误码 + 边界值
- 测试文件与被测文件同目录，命名 `test_*.py`
- 新增功能必须添加测试；变更后运行最相关测试，不必全量
- 判题 / 沙箱相关测试在无沙箱环境标注 skip 或 mock，注明原因

> 邮箱验证码：开发期未接入 SMTP，验证码打印在后端日志（`[email-code] ... code=xxxxxx`），便于本地联调。

## 生产检查清单

- [ ] 环境变量已配置且无默认弱值（`SECRET_KEY` / `MINIO_*` / 数据库密码）
- [ ] 数据库迁移已执行（`alembic upgrade head`）
- [ ] CORS 限制为实际域名
- [ ] HTTPS 已启用（含 MinIO `MINIO_SECURE=true`）
- [ ] `.env` 未提交到版本控制（见 `.gitignore`）
- [ ] 健康检查端点可访问（见 `docker/docker-compose.yml` 的 healthcheck）
- [ ] MinIO bucket 已创建且后端具备头像对象读写权限
- [ ] 沙箱节点已注册且健康（`GET /api/v1/sandbox/health`）

## 禁止事项

- 不硬编码 URL、端口、密钥
- 不在 Dockerfile 中写死环境变量值
- 不把 `.env` 打包进镜像
- 生产环境不暴露 `debug` 级别日志
- 测试点对象不向前端暴露下载 / 预签名 URL
