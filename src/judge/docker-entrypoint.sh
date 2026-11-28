#!/bin/sh
# 判题节点容器入口：准备 isolate 运行环境后 exec 传入命令。
#
# 两件必须在容器启动后做的事（构建期做不了）：
# 1. 创建 cgroup 根 /sys/fs/cgroup/isolate —— isolate 的 cg_root。
# 2. 在父层级打开 memory / pids 控制器委派，否则 isolate 建 box 子组时报
#    "Cannot write .../memory.max: No such file or directory"。
#
# 前提：容器以 --privileged --cgroupns=host 运行。私有 cgroup namespace 下
# 容器内 cgroup 根仍被容器 init 进程占用，cgroup v2 的"无内部进程"约束会让
# 控制器无法委派（写 subtree_control 报 EBUSY），isolate 随之无法建 box。
set -e

CG_PARENT=/sys/fs/cgroup
CG_ROOT=$CG_PARENT/isolate

if [ -f "$CG_PARENT/cgroup.controllers" ] && [ ! -d "$CG_ROOT" ]; then
    mkdir -p "$CG_ROOT" 2>/dev/null || {
        echo "judge-node: 无法创建 $CG_ROOT；需要 privileged 容器 + cgroupns=host + cgroup v2" >&2
        exit 1
    }
fi

enable_controller() {
    # $1 = cgroup 目录，$2 = 控制器名；父层级未提供该控制器时静默跳过
    dir=$1
    ctl=$2
    [ -f "$dir/cgroup.controllers" ] || return 0
    if ! grep -qw "$ctl" "$dir/cgroup.controllers"; then
        return 0
    fi
    if grep -qw "$ctl" "$dir/cgroup.subtree_control" 2>/dev/null; then
        return 0
    fi
    echo "+$ctl" > "$dir/cgroup.subtree_control" 2>/dev/null || true
}

# 父层级委派给 isolate 根，isolate 根再往下委派给各 box 子组
for ctl in memory pids; do
    enable_controller "$CG_PARENT" "$ctl"
    enable_controller "$CG_ROOT" "$ctl"
done

mkdir -p /run/isolate/locks /workspace /cache

exec "$@"
