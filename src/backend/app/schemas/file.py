"""文件上传请求/响应结构。"""
from __future__ import annotations

from pydantic import BaseModel


class AvatarUploadResult(BaseModel):
    """头像上传响应。"""

    oss_id: str
    url: str
    content_type: str
    size: int
