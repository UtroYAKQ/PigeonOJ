# 运行与运维（测试 · 部署 · 环境变量）

> 如何运行、测试与部署本项目，以及所有环境变量。涉及配置或发布变更时先读本文件。

## 一键启动（Windows）

双击仓库根目录的 `run-local.bat`：自动启动 PostgreSQL / MinIO / Redis 容器（本地镜像，不拉取），构建判题节点镜像（`pigeonoj/judge-node`，单镜像含 nsjail 沙箱层）并启动 1 个本地判题节点容器（首次自动复制 `.env.node.example` 为 `.env.node`），执行数据库迁移与演示账号引导，随后弹出两个窗口分别运行后端（8000，内含判题 gRPC 网关 :50051 与维护循环）与前端（5173，真实 API 模式）。

## 本地运行（不用 Docker）

依赖：Python 3.12+、Node 20+、本地 PostgreSQL / Redis / MinIO。

```bash
# 后端（判题 gRPC 网关 :50051 与维护循环随应用启动，需配置 JUDGE_GATEWAY_TOKENS）
cd src/backend && pip install -r requirements.txt && alembic upgrade head && python run.py

# 前端
cd src/frontend && npm install && npm run dev
```

- 后端：`http://localhost:8000`（API 前缀 `/api/v1`）
- 前端：`http://localhost:5173`（dev 模式通过 vite 代理把 `/api` 转发到 `localhost:8000`，前端相对路径 `/api/v1` 即可直连，无需处理 CORS）
- 注意：`vite.config.ts` 是唯一生效的 vite 配置 —— `vue-tsc -b` 的编译产物已重定向到 `node_modules/.vite-config/`，不会生成根目录 `vite.config.js` 抢占加载（vite 优先加载 `.js` 配置）

## Docker 运行

```bash
# 生产（后端 + 前端 + 基础设施；判题 gRPC 网关随后端进程启动）
docker compose -f docker/docker-compose.yml up -d

# 构建判题节点镜像（单镜像：nsjail 沙箱层 + gRPC 守护进程，一次构建）
docker build -t pigeonoj/judge-node src/judge

# 启动判题节点容器（在另一台服务器上部署时改 SERVER_ADDRESS 为后端公网地址；
# 配置模板 .env.node.example → 复制为 .env.node）
docker compose --env-file .env.node -f docker-compose-node.yml up -d --build
```

### 判题节点与沙箱说明

- **后端进程不执行任何用户代码**。代码执行只发生在 `pigeonoj/judge-node` 容器内；
  后端仅提供 gRPC 网关（`:50051`）做注册认证、负载均衡派发与结果落库。
- 节点镜像为单镜像（`src/judge/Dockerfile`）：Ubuntu 24.04 + 阿里云 APT 源 + nsjail 3.4 +
  Python/C++/Java 工具链 + grpcio + 守护进程，一次构建产出 `pigeonoj/judge-node`，无独立基础镜像。
- 节点固定挂载两个宿主机目录：工作区 → 容器 `/workspace`（每作业子目录自动创建/清理）、
  数据缓存 → 容器 `/cache`（按题目 data_version 复用）。绝不能配置为宿主机根目录、用户代码目录或 Docker socket。
- 节点需要 `privileged: true`（nsjail 嵌套 namespace）并**只做出站连接**后端网关；不开放任何入站端口。
- 配置来源：`src/judge/node/node.toml`，环境变量 `SERVER_ADDRESS / SERVER_TOKEN /
  JUDGE_NODE_ID / JUDGE_NODE_NAME / JUDGE_NODE_CAPACITY` 可覆盖。
- 执行语义：只允许源码和输入位于 `/workspace`，
  Python/C++/Java 编译与运行均在 nsjail 内完成；C++/Java 一次提交只编译一次，逐测试点独立运行。
- 正式判题限制由后端按 `sandbox_configs` 比例换算后随作业下发；不要把测试点期望输出或宿主机路径传给前端。

支持入口与执行规范见 [docs/contracts/judge.md](contracts/judge.md)。

## 后端配置文件

后端配置主文件是 `src/backend/backend.toml`（与判题节点 `node.toml` 同风格，随仓库提交、仅含开发默认值），
`src/backend/app/config.py` 只负责加载。加载优先级（高 → 低）：

1. 进程环境变量
2. `.env`（仓库根目录，仅放需要覆盖的项）
3. `backend.toml`

```toml
[app]     # environment / secret_key / log_level
[database]  # url
[redis]     # url
[minio]     # endpoint / access_key / secret_key / bucket / secure
[judge]     # gateway_tokens / grpc_host / grpc_port / heartbeat_interval_seconds
[cors]      # origins
```

- TOML 分段键拍平为下划线字段名：`[minio] endpoint` → 环境变量 `MINIO_ENDPOINT`
- 配置文件缺失时回落到环境变量；两者都缺则启动报错（fail fast）
- Docker 部署时 `backend.toml` 随构建上下文进入镜像（`/app/backend.toml`），
  敏感项用 `.env` / `environment:` 环境变量覆盖

## 环境变量

变量清单见 `backend.toml` 与 `.env.example`；`.env` 仅用于覆盖，本地使用：`cp .env.example .env`。

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ENVIRONMENT` | 运行环境（backend.toml `[app] environment`） | `development` / `production` |
| `SECRET_KEY` | 会话 / 加密主密钥（生产必改，backend.toml `[app] secret_key`） | 随机长字符串 |
| `LOG_LEVEL` | 日志级别（backend.toml `[app] log_level`） | `INFO` |
| `POSTGRES_USER` | PostgreSQL 用户（仅 docker compose 基础设施服务使用） | `pigeonoj` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码（仅 docker compose 基础设施服务使用） | `pigeonoj` |
| `POSTGRES_DB` | PostgreSQL 库名（仅 docker compose 基础设施服务使用） | `pigeonoj` |
| `DATABASE_URL` | PostgreSQL 连接串（backend.toml `[database] url`） | `postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj` |
| `REDIS_URL` | Redis 连接串（backend.toml `[redis] url`） | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | MinIO 端点（backend.toml `[minio] endpoint`） | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥（backend.toml `[minio] access_key`） | `pigeonoj` |
| `MINIO_SECRET_KEY` | MinIO 密钥（backend.toml `[minio] secret_key`） | `pigeonoj-minio-secret` |
| `MINIO_BUCKET` | MinIO 存储桶（backend.toml `[minio] bucket`） | `pigeonoj` |
| `MINIO_SECURE` | 是否启用 HTTPS（生产置 true，backend.toml `[minio] secure`） | `false` |
| `VITE_API_BASE_URL` | 前端 API 基址 | `http://localhost:8000/api/v1` |
| `JUDGE_GATEWAY_TOKENS` | 判题节点注册令牌，逗号分隔多个；为空则网关不启动（backend.toml `[judge] gateway_tokens`）。节点 node.toml 的 server.token 需匹配其一 | 空 |
| `JUDGE_GRPC_HOST` | 判题网关 gRPC 监听地址（backend.toml `[judge] grpc_host`） | `0.0.0.0` |
| `JUDGE_GRPC_PORT` | 判题网关 gRPC 监听端口（backend.toml `[judge] grpc_port`） | `50051` |
| `TEST_DATABASE_URL` | 测试库连接串（覆盖 pytest 默认的 pigeonoj_test） | `postgresql+asyncpg://pigeonoj:pigeonoj@localhost:5432/pigeonoj_test` |

> CORS 来源列表在 backend.toml `[cors] origins`（TOML 数组）；用环境变量覆盖时为 JSON 数组形式。

> 判题节点自身的配置（SERVER_ADDRESS / SERVER_TOKEN / JUDGE_NODE_ID / JUDGE_NODE_NAME /
> JUDGE_NODE_CAPACITY / NODE_WORKSPACE_DIR / NODE_CACHE_DIR）见模板 `.env.node.example`，
> 运行时默认值来自节点侧 `src/judge/node/node.toml`，环境变量可覆盖；不属于后端环境变量。

> 大模型配置不通过环境变量注入；AI 能力（含模型配置）暂缓实现，立项时再引入对应配置域。

## 测试

```bash
npm run lint:check       # 前端静态检查（ESLint flat config：eslint-plugin-vue + typescript-eslint）
pytest                  # 后端单元 + 集成测试（pytest + pytest-asyncio）
npm test                # 前端单元测试（Vitest + jsdom；utils / constants/dict / api http 层）
```

前端工程化约定（`src/frontend/`）：

- 格式化由 Prettier 负责（`.prettierrc.json`），`npm run format` 一键格式化；ESLint 关闭格式类规则（`@vue/eslint-config-prettier/skip-formatting`），双工具不打架
- ESLint 配置见 `eslint.config.js`（Vue essential + TS recommended）；`no-explicit-any` 暂关闭，存量清理后再开启
- Vitest 配置在 `vite.config.ts` 的 `test` 块：jsdom 环境（dict.ts / http.ts 依赖 localStorage 与 DOMPurify）；测试与被测文件同目录，命名 `*.spec.ts`
- ⚠️ 模板内联事件避免多条语句（如 `@click="a = 1; load()"`）：Prettier 折行后会生成非法模板表达式，统一收敛为 script 内方法

> 导入规则检查无外部依赖（纯标准库 AST），改动后端任何 import 后建议先跑它再跑 pytest；规则见 `docs/architecture.md` 分层架构与 `docs/decisions/2026-08-25-backend-service-repository-split.md`。

后端集成测试需要本地 PostgreSQL / Redis（`src/backend/tests/conftest.py`）：

- 默认连接 `pigeonoj_test` 库（自动 `drop_all` / `create_all` 重建表 + 种子角色/配置）与 Redis **db 15**
- ⚠️ **不要在跑 pytest 时把 `DATABASE_URL` 指向开发库** —— 测试会重建表结构；可用 `TEST_DATABASE_URL` 覆盖测试库
- pytest 配置（`pytest.ini`）：async 测试 / fixture 共享会话级事件循环（模块级异步引擎的连接池只绑定一个循环）

开发辅助脚本（`src/backend/scripts/`）：

```bash
python -m scripts.bootstrap_demo_users   # 引导演示账号 admin/tutor/user（开发期联调用）
python -m scripts.smoke_test             # 端到端冒烟（httpx ASGI 全链路）
python scripts/verify_db.py              # 校验迁移与种子数据
python scripts/check_import_rules.py     # 分层导入规则机械检查：api 不被下穿依赖、契约层与 utils 保持纯净
```

策略：

- 单元测试覆盖 Service 逻辑；集成测试覆盖 Route → Service → Repository 完整链路
- 每个端点覆盖：成功场景 + 每种错误码 + 边界值
- 测试文件与被测文件同目录，命名 `test_*.py`
- 新增功能必须添加测试；变更后运行最相关测试，不必全量
- 判题 / 沙箱相关测试在无沙箱环境标注 skip 或 mock，注明原因

> 邮箱验证码发信：系统配置 `email.smtp.host` 为空（默认）时未接入 SMTP，验证码打印在后端日志（`[email-code] ... code=xxxxxx`），便于本地联调；在管理后台「认证邮箱」域配置 SMTP 服务器后走真实邮件发送，发送失败返回 `5001`。

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
