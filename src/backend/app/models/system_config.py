"""平台级系统配置表：system_configs（docs/contracts/admin.md system_configs）。

系统配置是横切基础设施——中间件与各业务 Service 都要读取策略值，
模型独立于业务模块；读写服务见 app.services.system_config，
admin 路由仅提供管理端点（查询 / 修改）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.enums import ConfigCategory


class SystemConfig(Base):
    """系统配置：KV + 分域（docs/contracts/admin.md system_configs）。"""

    __tablename__ = "system_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # site / auth_email / team / contest / model / token / sandbox / log / community
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    config_key: Mapped[str] = mapped_column(String(128), nullable=False)
    config_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=lambda: datetime.now()
    )

    __table_args__ = (UniqueConstraint("category", "config_key", name="uq_system_configs_category_key"),)
