"""AI：聊天、改码、编译纠错、出题、Token 统计。

契约见 docs/contracts/ai.md（如存在）；题目内容经 app.modules.problems.api 读取，
Token 用量统计写入 user_token_stats。落地时对外能力经本包 api.py 暴露。
"""
