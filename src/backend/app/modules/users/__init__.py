"""认证 / 用户中心 / 用户管理：注册登录、账号生命周期、会话、全局角色、RBAC 判定。

契约见 docs/contracts/users.md（auth/users 端点）与 docs/contracts/admin.md（用户管理端点）；
涉及 users / user_sessions / roles / user_roles。原 auth 模块已并入本模块
（docs/decisions/2026-08-24-backend-module-packaging.md）。
跨模块只允许 from app.modules.users.api import ...。
"""
