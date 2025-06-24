from celery import Celery
from celery.schedules import crontab
from app.db import base  # noqa 使Worker启动时加载所有模型（另起终端，先设置环境变量-$env:RUNNING_IN_CELERY="true"，再启动Worker：celery -A app.core.celery_app worker -l info -P threads）
from app.core.config import settings

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.order_tasks", "app.tasks.seckill_tasks", "app.tasks.recommendation_tasks", "app.tasks.user_profile_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone='Asia/Shanghai',
    enable_utc=True,
)

# 设置 Celery Beat 调度器（另起终端：celery -A app.core.celery_app beat -l info）
celery_app.conf.beat_schedule = {
    # 每2分钟取消过期订单
    'cancel-overdue-orders-every-2-minutes': {
        'task': 'app.tasks.order_tasks.cancel_overdue_orders_task',
        'schedule': crontab(minute='*/2'),  # 每2分钟执行一次,测试
    },
    # 每分钟更新秒杀活动状态
    'update-seckill-status-every-minute': {
        'task': 'app.tasks.seckill_tasks.update_seckill_activity_status_task',
        'schedule': crontab(minute='*'),  # 每分钟执行一次
    },
    # 每日凌晨 03:00 生成商品相似度矩阵
    'generate-item-similarity-daily': {
        'task': 'app.tasks.recommendation_tasks.generate_item_similarity_task',
        'schedule': crontab(hour=17, minute=0),
    },
    # 每日凌晨 04:00 生成用户画像
    'generate-user-profiles-daily': {
        'task': 'app.tasks.user_profile_tasks.generate_user_profiles_task',
        'schedule': crontab(hour=17, minute=0),
    },
}
