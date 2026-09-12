# PigeonOJ 判题节点镜像（多阶段：编译 nsjail 后丢弃构建依赖）
#   docker build -t pigeonoj/judge-node src/judge
#   docker build --build-arg GH_MIRROR=https://gh-proxy.com/https://github.com/ -t pigeonoj/judge-node src/judge
ARG UBUNTU_IMAGE=docker.1ms.run/ubuntu:24.04
ARG NSJAIL_VERSION=3.4
ARG GH_MIRROR=

FROM ${UBUNTU_IMAGE} AS nsjail-build
ARG NSJAIL_VERSION
ARG GH_MIRROR
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       autoconf bison flex g++ git libprotobuf-dev libnl-route-3-dev \
       libseccomp-dev make pkg-config protobuf-compiler ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$GH_MIRROR" ]; then git config --global url."$GH_MIRROR".insteadOf "https://github.com/"; fi \
    && git clone --depth 1 --branch ${NSJAIL_VERSION} https://github.com/google/nsjail.git /tmp/nsjail \
    && make -C /tmp/nsjail \
    && install -m 0755 /tmp/nsjail/nsjail /usr/local/bin/nsjail

FROM ${UBUNTU_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       g++ python3.12 python3-pip openjdk-21-jdk-headless ca-certificates \
       libprotobuf32t64 libnl-route-3-200 libseccomp2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=nsjail-build /usr/local/bin/nsjail /usr/local/bin/nsjail

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin runner \
    && mkdir -p /workspace /runner \
    && chown -R runner:runner /workspace /runner

COPY node/requirements.txt /tmp/node-requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/node-requirements.txt

COPY sandbox/nsjail.cfg /etc/pigeonoj/nsjail.cfg
COPY sandbox/run-in-nsjail.sh /usr/local/bin/run-in-nsjail
RUN chmod 0755 /usr/local/bin/run-in-nsjail

COPY node /opt/judge-node
WORKDIR /opt/judge-node

ENTRYPOINT []
CMD ["python3.12", "daemon.py", "--config", "node.toml"]
