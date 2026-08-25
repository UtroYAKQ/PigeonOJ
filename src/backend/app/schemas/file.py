"""文件上传请求/响应结构。"""
from __future__ import annotations

from pydantic import BaseModel


class AvatarUploadResult(BaseModel):
    """头像上传响应。"""

    oss_id: str
    url: str
    content_type: str
    size: int


class ImageUploadResult(BaseModel):
    """公共图片上传响应（题面插图等 Markdown 引用场景）。"""

    oss_id: str
    url: str
    content_type: str
    size: int
