"""审计日志写入助手（兼容层，已迁移至 shared/audit.py）。

保留此文件以兼容旧有导入：
    from app.modules.admin.audit import write_login_log, write_request_log, write_exception_log

新代码请直接使用：
    from app.shared.audit import write_login_log, write_request_log, write_exception_log
"""
from __future__ import annotations

from app.shared.audit import write_exception_log, write_login_log, write_request_log

__all__ = ["write_login_log", "write_request_log", "write_exception_log"]
