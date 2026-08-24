"""admin 模块对外门面（唯一出口）。

当前无跨模块业务能力（配置读取走 shared.infra.system_config 平台设施，
审计写入走 shared.infra.audit）；保留门面以维持统一的模块通信约定。
"""

__all__: list[str] = []
