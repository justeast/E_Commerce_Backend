from celery import Celery
from celery.schedules import crontab
from app.db import base  # noqa 使Worker启动时加载所有模型（另起终端：celery -A app.core.celery_app worker -l info -P threads）
from app.core.config import settings

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.order_tasks"]
)

celery_app.conf.update(
    task_track_started=True,
    timezone='Asia/Shanghai',
    enable_utc=True,
)

# 设置 Celery Beat 调度器（另起终端：celery -A app.core.celery_app beat -l info）
celery_app.conf.beat_schedule = {
    'cancel-overdue-orders-every-2-minutes': {
        'task': 'app.tasks.order_tasks.cancel_overdue_orders_task',
        'schedule': crontab(minute='*/2'),  # 每2分钟执行一次,测试
    },
}
