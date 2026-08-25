# PigeonOJ 判题节点镜像（单镜像，一次构建）：
#   nsjail 沙箱层（Ubuntu 24.04 + nsjail 3.4 + Python/C++/Java 工具链）
#   + gRPC 守护进程（node/daemon.py）
FROM docker.1ms.run/ubuntu:24.04

ARG NSJAIL_VERSION=3.4
# 受限网络下可用 GitHub 加速镜像覆盖所有 git 访问（含 nsjail 内部拉取的 kafel 子依赖）：
#   docker build --build-arg GH_MIRROR=https://gh-proxy.com/https://github.com/ -t pigeonoj/judge-node src/judge
ARG GH_MIRROR=
ENV DEBIAN_FRONTEND=noninteractive

# 编译工具链与判题语言运行时；Debian 包走阿里云镜像（基础镜像经上面 ARG 代理拉取）
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       autoconf bison flex g++ git libprotobuf-dev libnl-route-3-dev \
       libseccomp-dev make pkg-config protobuf-compiler python3.12 \
       python3.12-dev python3-pip openjdk-21-jdk-headless ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# nsjail 源码构建并安装到 PATH
RUN if [ -n "$GH_MIRROR" ]; then git config --global url."$GH_MIRROR".insteadOf "https://github.com/"; fi \
    && git clone --depth 1 --branch ${NSJAIL_VERSION} https://github.com/google/nsjail.git /tmp/nsjail \
    && make -C /tmp/nsjail \
    && install -m 0755 /tmp/nsjail/nsjail /usr/local/bin/nsjail \
    && rm -rf /tmp/nsjail

# 判题工作区目录；runner 用户保留用于人工调试（守护进程以 root 运行）
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin runner \
    && mkdir -p /workspace /runner \
    && chown -R runner:runner /workspace /runner

# gRPC 守护进程依赖
RUN pip3 install --no-cache-dir --break-system-packages grpcio protobuf

# 沙箱配置与调试包装脚本（判题链路不经过 run-in-nsjail，仅人工调试用）
COPY sandbox/nsjail.cfg /etc/pigeonoj/nsjail.cfg
COPY sandbox/run-in-nsjail.sh /usr/local/bin/run-in-nsjail
RUN chmod 0755 /usr/local/bin/run-in-nsjail

COPY node /opt/judge-node
WORKDIR /opt/judge-node

# 运行要求（见 docker-compose-node.yml）：
#   privileged: true                —— nsjail 嵌套 namespace 所需
#   -v <宿主机工作区>:/workspace     —— 任务临时目录
#   -v <宿主机缓存>:/cache          —— 题目数据缓存
#   SERVER_ADDRESS / SERVER_TOKEN   —— 后端网关地址与注册令牌
ENTRYPOINT []
CMD ["python3.12", "daemon.py", "--config", "node.toml"]
