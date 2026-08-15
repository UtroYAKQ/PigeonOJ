"""沙箱：安全执行环境、自动调度、样例执行接口。

契约见 docs/contracts/judge.md（判题执行规范）与 docs/contracts/problems.md（自测）；
代码仅在 nsjail 沙箱内执行。涉及 sandbox_configs（语言级运行参数与判题限制比例）与节点状态。
"""
