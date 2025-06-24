from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.db.session import async_session
from app.services.recommendation_service import recommendation_service

logger = get_task_logger(__name__)


@celery_app.task
def generate_item_similarity_task(days: int = 30, top_k: int = 20):
    """
    离线生成商品相似度矩阵并写入 Redis
    """

    async def _run():
        async with async_session() as db:  # AsyncSession
            from app.core.redis_client import get_redis_pool  # 延迟导入避免循环
            redis = await get_redis_pool()
            try:
                logger.info("开始生成商品相似度矩阵...")
                await recommendation_service.generate_item_similarity(
                    db=db, redis=redis, days=days, top_k=top_k
                )
                logger.info("生成商品相似度矩阵成功")
            finally:
                await redis.close()

    import asyncio
    asyncio.run(_run())
