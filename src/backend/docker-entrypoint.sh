#!/bin/sh
# 后端容器启动入口：先执行数据库迁移（fail fast，迁移失败不启动应用），再启动服务。
set -e
cd /app
echo "[entrypoint] applying database migrations..."
alembic upgrade head
echo "[entrypoint] migrations done"
exec "$@"
