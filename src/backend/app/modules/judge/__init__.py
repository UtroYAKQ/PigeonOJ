"""判题：提交、调度、判题结果。

契约见 docs/contracts/judge.md；涉及 submissions / submission_test_case_results，
判题经 Celery 调度至沙箱执行；限制以 C++ 为基准，按 sandbox_configs 语言比例换算有效限制。
"""
