"""系统配置服务（兼容层，已迁移至 shared/common/config.py）。

保留此文件以兼容旧有导入：
    from app.shared.config import ConfigService, get_config_service

新代码请直接使用：
    from app.shared.common.config import ConfigService, get_config_service
"""
from app.shared.common.config import ConfigService, EMAIL_CODE_DEFAULT, get_config_service  # noqa: F401

__all__ = ["ConfigService", "EMAIL_CODE_DEFAULT", "get_config_service"]
