"""Celery 应用：worker + beat 入口。

对应 docker-compose.yml 中 celery 服务命令 `celery -A app.worker.celery_app`。
骨架阶段不含任何任务；后续按 docs/architecture.md 的 Celery 任务表接入
（判题调度、比赛封榜、出题生成等），任务模块在 include 中声明。
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pigeonoj",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[],  # 任务模块在此声明，如 "app.modules.judge.tasks"
)

celery_app.conf.update(
    timezone="Asia/Shanghai",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
