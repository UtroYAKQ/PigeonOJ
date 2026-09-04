# 后端镜像：python:3.12-slim + uvicorn
# 构建上下文为 src/backend（见 docker/docker-compose.yml）
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先拷贝依赖清单安装，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用代码
COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# 生产默认启动命令（判题 gRPC 网关随应用 lifespan 启动）；
# ENTRYPOINT 先执行数据库迁移（fail fast），再 exec 本 CMD
ENTRYPOINT ["/app/docker-entrypoint.sh"]
# proxy-headers：nginx 反代后用 X-Forwarded-For 重写 client.host；
# forwarded-allow-ips=all 限定 compose 内网（容器网络不可公网直达）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
