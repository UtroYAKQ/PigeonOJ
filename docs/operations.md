# 运行与运维（测试 · 部署 · 环境变量）

> 如何运行、测试与部署本项目，以及所有环境变量。涉及配置或发布变更时先读本文件。

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
- 前端：`http://localhost:5173`

## Docker 运行

```bash
# 开发（PostgreSQL + Redis + MinIO + 后端热重载；前端本地 npm run dev）
docker compose -f docker/docker-compose-dev.yml up --build

# 生产（后端 + Celery + 前端 + 基础设施）
docker compose -f docker/docker-compose.yml up -d
```

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
| `VITE_API_BASE_URL` | 前端 API 基址 | `http://localhost:8000/api/v1` |

> 大模型配置（各 AI 能力所用模型、API Key）在 `system_configs` / `model_configs` 中管理（Key 加密存储），不通过环境变量注入；`.env.example` 仅提供提供方级兜底 Key 的可选项。

## 测试

```bash
pytest                  # 后端单元 + 集成测试（pytest + pytest-asyncio）
npm test                # 前端单元测试（Vitest）
```

策略：

- 单元测试覆盖 Service 逻辑；集成测试覆盖 Route → Service → Repository 完整链路
- 每个端点覆盖：成功场景 + 每种错误码 + 边界值
- 测试文件与被测文件同目录，命名 `test_*.py`
- 新增功能必须添加测试；变更后运行最相关测试，不必全量
- 判题 / 沙箱相关测试在无沙箱环境标注 skip 或 mock，注明原因

## 生产检查清单

- [ ] 环境变量已配置且无默认弱值（`SECRET_KEY` / `MINIO_*` / 数据库密码）
- [ ] 数据库迁移已执行（`alembic upgrade head`）
- [ ] CORS 限制为实际域名
- [ ] HTTPS 已启用（含 MinIO `MINIO_SECURE=true`）
- [ ] `.env` 未提交到版本控制（见 `.gitignore`）
- [ ] 健康检查端点可访问（见 `docker/docker-compose.yml` 的 healthcheck）
- [ ] 沙箱节点已注册且健康（`GET /api/v1/sandbox/health`）

## 禁止事项

- 不硬编码 URL、端口、密钥
- 不在 Dockerfile 中写死环境变量值
- 不把 `.env` 打包进镜像
- 生产环境不暴露 `debug` 级别日志
- 测试点对象不向前端暴露下载 / 预签名 URL
