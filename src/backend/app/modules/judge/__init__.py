"""判题：提交、验题提交、调度、判题结果、沙箱语言配置。

契约见 docs/contracts/judge.md；涉及 submissions / submission_test_case_results /
sandbox_configs。题目 / 测试点 / 验题记录实体在 problems 模块，本模块只经
`app.modules.problems.api` 读取（依赖方向：judge → problems，单向）。
判题经 gRPC 节点网关派发至判题节点容器内 nsjail 执行；限制以 C++ 为基准，
按 sandbox_configs 语言比例换算有效限制。
"""
