FROM docker.1ms.run/ubuntu:24.04

ARG NSJAIL_VERSION=3.4
# 受限网络下可用 GitHub 加速镜像覆盖所有 git 访问（含 nsjail 内部拉取的 kafel 子依赖）：
#   docker build --build-arg GH_MIRROR=https://gh-proxy.com/https://github.com/ -t sandbox:local src/judge/sandbox
ARG GH_MIRROR=
ENV DEBIAN_FRONTEND=noninteractive

# Use a mainland mirror for Debian packages; the base image itself is proxied above.
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       autoconf bison flex g++ git libprotobuf-dev libnl-route-3-dev \
       libseccomp-dev make pkg-config protobuf-compiler python3.12 \
       python3.12-dev openjdk-21-jdk-headless ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "$GH_MIRROR" ]; then git config --global url."$GH_MIRROR".insteadOf "https://github.com/"; fi \
    && git clone --depth 1 --branch ${NSJAIL_VERSION} https://github.com/google/nsjail.git /tmp/nsjail \
    && make -C /tmp/nsjail \
    && install -m 0755 /tmp/nsjail/nsjail /usr/local/bin/nsjail \
    && rm -rf /tmp/nsjail

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin runner \
    && mkdir -p /sandbox /runner \
    && chown -R runner:runner /sandbox /runner

COPY nsjail.cfg /etc/pigeonoj/nsjail.cfg
COPY run-in-nsjail.sh /usr/local/bin/run-in-nsjail
RUN chmod 0755 /usr/local/bin/run-in-nsjail

WORKDIR /sandbox
ENTRYPOINT ["/usr/local/bin/run-in-nsjail"]
