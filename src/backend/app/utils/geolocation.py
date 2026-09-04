"""IP 地理位置解析（离线）：ip2region xdb 数据文件，location 形如「中国|0|浙江省|杭州市|阿里云」。

数据文件 `app/data/ip2region.xdb`（v2.11，11MB，随仓库分发）；
py-ip2region v3 的 Searcher 以 file 模式打开（每次查询 1~2 次磁盘 IO，无内存驻留压力），
进程生命周期内单例复用。查询失败 / 文件缺失一律返回 None，不影响日志主流程。
数据更新：从 ip2region 官方仓库（lionsoul2014/ip2region）重新下载 xdb 覆盖本文件即可。
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_XDB_PATH = Path(__file__).resolve().parent.parent / "data" / "ip2region.xdb"

_searcher = None
_lock = Lock()
_missing = False


def _get_searcher():
    global _searcher, _missing
    if _searcher is not None or _missing:
        return _searcher
    with _lock:
        if _searcher is not None or _missing:
            return _searcher
        if not _XDB_PATH.exists():
            logger.warning("ip2region.xdb 缺失（%s），location 将为空", _XDB_PATH)
            _missing = True
            return None
        try:
            # 延迟导入：保持依赖可选性（未安装 py-ip2region 时日志功能不受影响）
            from ip2region import util
            from ip2region import searcher as _searcher_mod

            version = util.version_from_header(util.load_header_from_file(str(_XDB_PATH)))
            _searcher = _searcher_mod.new_with_file_only(version, str(_XDB_PATH))
        except Exception:  # noqa: BLE001 - 初始化失败不影响主流程
            logger.exception("ip2region searcher 初始化失败")
            _missing = True
        return _searcher


def lookup_location(ip: str | None) -> str | None:
    """IP → 位置字符串「国家|区域|省份|城市|ISP」；内网返回「内网」；失败返回 None。

    结果直接存日志表 location 列，前端原样展示；解析失败不影响请求主流程。
    """
    if not ip:
        return None
    searcher = _get_searcher()
    if searcher is None:
        return None
    try:
        raw = searcher.search(ip)
    except Exception:  # noqa: BLE001 - 单次查询失败不影响主流程
        return None
    if not raw:
        return None
    # xdb 返回「国家|区域|省份|城市|ISP」，0 为占位；压缩为「中国 浙江省 杭州市 阿里云」形态；
    # 内网段 xdb 返回「0|0|0|内网IP|内网IP」，去重后统一记「内网IP」
    parts = [p for p in raw.split("|") if p and p != "0"]
    if not parts:
        return None
    return " ".join(dict.fromkeys(parts))
