# Alembic 迁移

本目录存放数据库迁移脚本，**表结构唯一来源是迁移 SQL**（见 `docs/contracts/index.md` 与 `docs/architecture.md`）。

骨架阶段无业务表，目录暂空。后续按各模块契约手写迁移（或对已接入的
`target_metadata` 使用 `alembic revision --autogenerate`），每次迁移必须：

1. 提供 `upgrade()` / `downgrade()`；
2. 同步更新 `docs/contracts/` 对应模块的表结构说明。
