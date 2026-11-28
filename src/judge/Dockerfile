# PigeonOJ 判题节点镜像（多阶段：构建 isolate 后丢弃构建依赖）
#   docker build -t pigeonoj/judge-node src/judge
#   docker build --build-arg GH_MIRROR=https://gh-proxy.com/https://github.com/ -t pigeonoj/judge-node src/judge
# 运行要求：Linux 宿主 + cgroup v2 + privileged（isolate 需要创建 namespace 与 cgroup）
ARG UBUNTU_IMAGE=docker.1ms.run/ubuntu:24.04
ARG ISOLATE_VERSION=2.1
ARG GH_MIRROR=

FROM ${UBUNTU_IMAGE} AS isolate-build
ARG ISOLATE_VERSION
ARG GH_MIRROR
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential git libcap-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$GH_MIRROR" ]; then git config --global url."$GH_MIRROR".insteadOf "https://github.com/"; fi \
    && git clone --depth 1 --branch v${ISOLATE_VERSION} https://github.com/ioi/isolate.git /tmp/isolate \
    # default.cf 由 default.cf.in 生成（Makefile 模式规则），不能直接 install
    && make -C /tmp/isolate isolate default.cf \
    # 容器内以 root 运行，无需 setuid 位
    && install -m 0755 /tmp/isolate/isolate /usr/local/bin/isolate \
    && install -m 0644 /tmp/isolate/default.cf /usr/local/etc/isolate

FROM ${UBUNTU_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       g++ python3.12 python3-pip openjdk-21-jdk-headless ca-certificates \
       libcap2 util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY --from=isolate-build /usr/local/bin/isolate /usr/local/bin/isolate
COPY --from=isolate-build /usr/local/etc/isolate /usr/local/etc/isolate

# isolate 需要一段专用 UID/GID 用于 box 内身份（default.cf 的 subid_user=isolate）；
# 容器内以 root 运行、无需 setuid，box 根目录由 isolate 自管。
# cgroup v2：默认 cg_root 是 auto:/run/isolate/cgroup（依赖 isolate-cg-keeper/systemd），
# 容器内改用显式路径并挂载父层级，否则 --init 报 "Cannot open /run/isolate/cgroup"。
RUN mkdir -p /workspace /cache /var/local/lib/isolate /run/isolate/locks \
    && echo "isolate:100000:1000" > /etc/subuid \
    && echo "isolate:100000:1000" > /etc/subgid \
    && sed -i -e 's|^cg_root.*|cg_root = /sys/fs/cgroup/isolate|' /usr/local/etc/isolate \
    && python3.12 -c "import sys; print(sys.version)"

COPY node/requirements.txt /tmp/node-requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/node-requirements.txt

COPY node /opt/judge-node
WORKDIR /opt/judge-node

# 运行期入口：isolate 的 cg_root（/sys/fs/cgroup/isolate）必须在容器启动后创建
# ——构建期无法创建（镜像不保留 /sys 内容），仅 privileged 容器可写。
COPY docker-entrypoint.sh /usr/local/bin/judge-node-entrypoint
RUN chmod 0755 /usr/local/bin/judge-node-entrypoint

ENTRYPOINT ["/usr/local/bin/judge-node-entrypoint"]
CMD ["python3.12", "daemon.py", "--config", "node.toml"]
