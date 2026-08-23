# 本地 nsjail Docker 节点

## 状态

已采纳（本地开发 / 集成验证）。

## 背景

PigeonOJ 的代码执行必须经过 nsjail，并且默认禁用网络。仓库当前只有后端和基础设施编排，没有可直接验证 nsjail 约束的节点镜像。

## 决策

新增 `src/sandbox` 镜像和独立的 `docker/docker-compose-sandbox.yml`：

- 容器使用 Ubuntu 24.04，安装 Python 3.12、G++、JDK 21 与 nsjail。
- Compose 使用 `network_mode: none`，并以 `privileged: true` 提供 nsjail 在 Docker Desktop / Linux 上创建 namespace 所需的能力。
- nsjail 使用 user / mount / pid / ipc / uts / network namespace，限制 CPU、地址空间、进程数、文件大小和 CPU 核数。
- 运行器只接受 `/sandbox` 下的源码和输入路径；编译和执行均在 nsjail 内完成。
- 沙箱工作区使用独立 Docker volume，不挂载宿主机源码目录；镜像只读，运行时仅工作区和小型 tmpfs 可写。

## 风险与边界

`privileged: true` 是本地 Docker 节点的宿主机信任边界，不应将该 Compose 文件直接用于生产或暴露执行 API。生产部署需要单独的节点编排、最小 capability、资源配额、任务鉴权和健康检查实现。nsjail 配置中的限制是默认值，正式判题仍需由后端按 `sandbox_configs` 和题目限制生成每次执行参数。
