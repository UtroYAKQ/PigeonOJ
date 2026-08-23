# 沙箱 Docker 包装执行模式与 nsjail 环境修复

## 状态

已采纳（2026-08-23 排查「沙箱执行失败」得出）。

## 背景

本地 Windows 开发机没有 nsjail 二进制，`POST /sandbox/sample-run` 与 Judge Worker 直接 `subprocess.run(["nsjail", …])` 必然失败（503）。`sandbox:local` 镜像内已有完整工具链，但后端从未接入容器链路。逐层排查还发现 nsjail 配置本身的三处缺陷（compose 冒烟只覆盖 Python，C++/Java 从未真正验证过）：

1. jail 内没有 `/dev/null`（gcc 驱动重定向子进程 stdio 失败，误报 execvp ENOENT）；
2. `mount_proc: false` 导致无 `/proc/self/exe`，glibc 无法展开 RPATH 的 `$ORIGIN`，OpenJDK launcher 报 libjli.so 缺失；
3. `rlimit_as: 512` 小于 JVM 的虚拟地址预留（堆 + ClassSpace + CodeCache），VM 初始化直接失败——内存判据按契约是峰值 RSS，AS 上限只用于兜底。

另有两个工具链定位问题：gcc 驱动从 argv[0] 推导安装前缀，裸名调用在 jail 内推导失败退化为 PATH 搜索；OpenJDK launcher 沿 `/usr/bin/javac` 符号链解析 JAVA_HOME 失败。

## 决策

- 新增配置 `SANDBOX_DOCKER_IMAGE`：非空时 `NsjailExecutor.build_args` 把命令包装为
  `docker run --rm -i --network none --privileged --read-only -v <JUDGE_WORKSPACE_ROOT>:/sandbox --entrypoint nsjail <image> …`，
  与 `docker-compose-sandbox.yml` 的隔离参数一致；留空保持宿主机直跑形态（Linux 判题节点）。
  容器内经 `/bin/sh -c` 转发目标命令（nsjail 的 execve 不做 PATH 查找）。
- 工具链命令改为绝对路径并加 `-B/usr/bin/`（g++）、直接使用 JVM 真实路径（java/javac），消除前缀推导歧义。
- `nsjail.cfg` 修复：挂载只读 `/dev`、`mount_proc: true`、`rlimit_as: 4096`。
- `run-local.bat` 为后端窗口注入 `SANDBOX_DOCKER_IMAGE / NSJAIL_CONFIG_PATH / JUDGE_WORKSPACE_ROOT`。

## 后果

- Windows/macOS 本地开发全链路（样例自测 + 正式判题 Worker）可用；生产判题节点不设置该变量，行为不变。
- 每次执行起一个容器的秒级开销仅存在于本地开发模式。
- `privileged` 仍限于本机受控环境（沿用 2026-08-18-local-nsjail-docker 决策的边界声明）。
