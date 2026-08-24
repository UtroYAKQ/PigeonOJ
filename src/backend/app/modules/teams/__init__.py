"""团队：建队、邀请、成员、团队角色、解散。

契约见 docs/contracts/teams.md；涉及 teams / team_members / team_member_applications。
团队角色经 user_roles（scope='team'）表达，RBAC 判定复用 users 模块（users.api）。
落地时对外能力经本包 api.py 暴露。
"""
