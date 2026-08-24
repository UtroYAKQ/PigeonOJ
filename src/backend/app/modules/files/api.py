"""files 模块对外门面（唯一出口）。

头像 / SPJ 等文件上传能力；其他模块需要写 MinIO 时经此处调用，
对象 key 由服务端按 docs/architecture.md 存储规范生成。
"""
from app.modules.files.service import FileService

__all__ = ["FileService"]
