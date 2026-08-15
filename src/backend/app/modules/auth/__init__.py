"""认证 / 用户中心：注册、登录、账号生命周期、会话。

契约见 docs/contracts/users.md；涉及 users / user_sessions；邮箱验证码存 Redis（短 TTL），不落库。
"""
