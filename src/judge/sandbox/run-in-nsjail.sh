#!/bin/sh
# 便捷包装：在判题节点容器内以默认沙箱配置运行 nsjail（人工调试用）。
#
# 判题链路本身不经过本脚本 —— node/executor.py 直接调用 nsjail 二进制并显式传参。
# 本脚本仅保证缺省带上 /etc/pigeonoj/nsjail.cfg：
#   run-in-nsjail --time_limit 5 -- /bin/sh -c 'g++ -o a main.cpp && ./a'
# 等价于：
#   nsjail --config /etc/pigeonoj/nsjail.cfg --time_limit 5 -- /bin/sh -c '...'
set -eu

NSJAIL_CONFIG="${NSJAIL_CONFIG:-/etc/pigeonoj/nsjail.cfg}"

has_config=0
for arg in "$@"; do
    case "$arg" in
        --config | --config=* | -H)
            has_config=1
            break
            ;;
    esac
done

if [ "$has_config" -eq 0 ]; then
    set -- --config "$NSJAIL_CONFIG" "$@"
fi

exec nsjail "$@"
