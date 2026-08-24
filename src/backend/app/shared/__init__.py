"""共享层：纯技术设施，不依赖任何业务模块（docs/architecture.md Shared 层）。

## 分包结构

```
shared/
  infra/               # 基础设施层
    database.py        # 异步数据库连接
    redis.py           # Redis 客户端
    storage.py         # MinIO 对象存储
    logging.py         # 日志配置
    system_config.py   # 平台表：system_configs 模型 + 读写服务
    audit.py           # 平台表：request/login/exception_logs 模型 + 写入助手
  auth/
    security.py        # 安全工具（密码哈希、Token）
  common/              # 通用工具层
    errors.py          # 错误码常量与业务异常
    response.py        # 统一响应信封
    pagination.py      # 通用分页工具
    validation.py      # 参数校验
```

认证依赖（get_current_user 等）与 RBAC 权限判定属业务逻辑，
位于 app/modules/users（deps.py / permissions.py），经其 api.py 对外暴露。
"""
