"""文件上传请求/响应结构。"""
from __future__ import annotations

from pydantic import BaseModel


class AvatarUploadResult(BaseModel):
    """头像上传响应：url 为站内文件 URL，供 avatar_url 直接存储/渲染。"""

    url: str
    content_type: str
    size: int


class ImageUploadResult(BaseModel):
    """公共图片上传响应（题面插图等 Markdown 引用场景）：url 为站内文件 URL。"""

    url: str
    content_type: str
    size: int
