"""业务模块包。

每个模块对应 docs/architecture.md 的一个领域上下文，包含：
routes.py / service.py / repository.py / models.py / schemas.py 与对外门面 api.py。

模块通信约定（docs/decisions/2026-08-24-backend-module-packaging.md）：
- 跨模块只允许 import 对方包的 `api.py`（唯一出口），其余文件视为私有
- 依赖方向保持无环：users ← files/problems/admin；problems ← judge；
  shared/infra 为平台设施（系统配置、审计日志），可被任意层引用
- 由 scripts/check_import_rules.py 机械检查
"""
