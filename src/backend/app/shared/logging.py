"""日志配置（兼容层，已迁移至 shared/infra/logging.py）。

保留此文件以兼容旧有导入：
    from app.shared.logging import setup_logging

新代码请直接使用：
    from app.shared.infra.logging import setup_logging
"""
from app.shared.infra.logging import setup_logging  # noqa: F401

__all__ = ["setup_logging"]
