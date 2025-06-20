import asyncio
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.session import get_db, engine
from app.models.seckill import SeckillActivity, SeckillActivityStatus

logger = get_task_logger(__name__)


async def _async_update_seckill_status():
    """
    核心异步逻辑：更新秒杀活动状态。
    """
    logger.info("开始执行秒杀活动状态更新任务...")
    async_db_gen = get_db()
    session: AsyncSession = await anext(async_db_gen)

    try:
        async with session.begin():
            now = celery_app.now()

            # 1. 将已开始但状态仍为 PENDING 的活动更新为 ACTIVE
            stmt_to_active = (
                update(SeckillActivity)
                .where(
                    SeckillActivity.status == SeckillActivityStatus.PENDING,
                    SeckillActivity.start_time <= now,
                )
                .values(status=SeckillActivityStatus.ACTIVE)
            )
            result_to_active = await session.execute(stmt_to_active)
            updated_to_active = result_to_active.rowcount

            # 2. 将已结束但状态仍为 ACTIVE 的活动更新为 ENDED
            stmt_to_ended = (
                update(SeckillActivity)
                .where(
                    SeckillActivity.status == SeckillActivityStatus.ACTIVE,
                    SeckillActivity.end_time <= now,
                )
                .values(status=SeckillActivityStatus.ENDED)
            )
            result_to_ended = await session.execute(stmt_to_ended)
            updated_to_ended = result_to_ended.rowcount

        if updated_to_active > 0:
            logger.info(f"{updated_to_active}个秒杀活动状态已更新为 ACTIVE")
        if updated_to_ended > 0:
            logger.info(f"{updated_to_ended}个秒杀活动状态已更新为 ENDED")
        if updated_to_active == 0 and updated_to_ended == 0:
            logger.info("没有需要更新状态的秒杀活动。")

        return f"更新完成: {updated_to_active} 个变为ACTIVE, {updated_to_ended} 个变为ENDED。"

    finally:
        await async_db_gen.aclose()


async def _run_task_and_dispose():
    """
    异步包装器：运行业务逻辑，并确保在同一事件循环中销毁引擎
    """
    try:
        return await _async_update_seckill_status()
    finally:
        logger.info("正在销毁数据库引擎连接池(seckill task)")
        await engine.dispose()


@celery_app.task
def update_seckill_activity_status_task():
    """
    同步的 Celery 任务，用于更新秒杀活动状态。
    """
    logger.info("启动秒杀活动状态更新任务...")
    try:
        result = asyncio.run(_run_task_and_dispose())
        logger.info(f"任务完成: {result}")
        return result
    except Exception as e:
        logger.error(f"运行秒杀活动状态更新任务时发生严重错误: {e}", exc_info=True)
        raise
