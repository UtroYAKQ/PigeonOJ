"""共享层：响应信封、错误类、日志、RBAC 中间件、配置。

对应 docs/architecture.md 的 Shared 层；不得依赖任何业务模块。

## 分包结构

```
shared/
  infra/           # 基础设施层（数据库、Redis、存储、日志）
    database.py    # 异步数据库连接
    redis.py       # Redis 客户端
    storage.py     # MinIO 对象存储
    logging.py     # 日志配置
  auth/            # 认证授权层
    deps.py        # 依赖注入（get_current_user 等）
    permissions.py # 权限检查（MANAGER_ROLE_CODES 等）
    security.py    # 安全工具（密码哈希、Token）
  common/          # 通用工具层
    errors.py      # 错误码常量与业务异常
    response.py    # 统一响应信封
    pagination.py  # 通用分页工具
    validation.py  # 参数校验
    config.py      # 配置服务
    audit.py       # 审计日志
```

## 兼容层

原 shared/ 根目录下的文件保留为兼容层，内部 re-export 新路径的内容。
新代码请直接使用新的导入路径。
"""
