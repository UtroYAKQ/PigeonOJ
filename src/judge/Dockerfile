# PigeonOJ 判题节点镜像 = 沙箱基础镜像（nsjail + Python/C++/Java 工具链）+ gRPC 守护进程
# 基础镜像构建：docker build -t sandbox:local src/judge/sandbox
FROM sandbox:local

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages grpcio protobuf

COPY node /opt/judge-node
WORKDIR /opt/judge-node

# 运行要求（见 docker/docker-compose-node.yml）：
#   privileged: true                —— nsjail 嵌套 namespace 所需
#   -v <宿主机工作区>:/workspace     —— 任务临时目录
#   -v <宿主机缓存>:/cache          —— 题目数据缓存
#   SERVER_ADDRESS / SERVER_TOKEN   —— 后端网关地址与注册令牌
ENTRYPOINT []
CMD ["python3.12", "daemon.py", "--config", "node.toml"]
