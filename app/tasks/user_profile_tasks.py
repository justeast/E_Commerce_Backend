from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.db.session import async_session
from app.services.user_profile_service import user_profile_service

logger = get_task_logger(__name__)


@celery_app.task
def generate_user_profiles_task(days: int = 30):
    """
    周期生成 / 更新用户画像标签
    """

    async def _run():
        async with async_session() as db:
            logger.info("开始生成/更新用户画像标签...")
            await user_profile_service.aggregate_and_upsert_tags(db=db, days=days)
            logger.info("用户画像标签生成/更新完成")

    import asyncio
    asyncio.run(_run())
