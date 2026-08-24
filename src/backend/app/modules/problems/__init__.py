"""题库：题目 CRUD、可见性控制、测试点、验题（含题单规划占位）。

契约见 docs/contracts/problems.md；涉及 problems / test_cases / problem_tags /
problem_verifications 与验题邀请表。原题单（problem_sets）规划并入本模块。
判题执行链路在 judge 模块；本模块对 judge 暴露查询与验题状态回写钩子（api.py）。

跨模块约定（docs/decisions/2026-08-24-backend-module-packaging.md）：
其他模块只允许 from app.modules.problems.api import ...。
"""
