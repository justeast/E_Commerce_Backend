import asyncio
from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.session import get_db, engine
from app.models.order import Order, OrderStatusEnum
from app.services.order_service import order_service

# 使用 Celery 的标准日志记录器
logger = get_task_logger(__name__)

# 订单超时时间
ORDER_OVERDUE_MINUTES = 5  # 测试


async def _async_cancel_overdue_orders():
    """
    包含核心异步逻辑的辅助函数，仅负责业务逻辑
    """
    logger.info("正在执行取消超时订单的业务逻辑...")
    async_db_gen = get_db()
    session: AsyncSession = await anext(async_db_gen)
    cancelled_count = 0
    try:
        async with session.begin():
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=ORDER_OVERDUE_MINUTES)
            stmt = select(Order.order_sn).where(
                Order.status == OrderStatusEnum.PENDING_PAYMENT,
                Order.created_at < cutoff_time
            )
            result = await session.execute(stmt)
            overdue_order_sns = result.scalars().all()
            total_found = len(overdue_order_sns)

            if not overdue_order_sns:
                logger.info("没有找到需要取消的超时订单")
            else:
                logger.info(f"找到 {total_found} 个待取消的超时订单: {overdue_order_sns}")
                for order_sn in overdue_order_sns:
                    try:
                        await order_service.cancel_order(db=session, order_sn=order_sn)
                        logger.info(f"已准备取消超时订单: {order_sn}")
                        cancelled_count += 1
                    except Exception as e:
                        logger.error(f"取消超时订单 {order_sn} 失败: {e}", exc_info=True)

        if total_found == 0:
            return "没有找到需要取消的超时订单。"
        return f"成功取消 {cancelled_count}/{total_found} 个订单"

    finally:
        await async_db_gen.aclose()


async def _run_task_and_dispose():
    """
    异步包装器：运行业务逻辑，并确保在同一事件循环中销毁引擎
    """
    try:
        return await _async_cancel_overdue_orders()
    finally:
        logger.info("正在销毁数据库引擎连接池")
        await engine.dispose()


@celery_app.task
def cancel_overdue_orders_task():
    """
    同步的 Celery 任务，通过 一次 asyncio.run() 来启动和运行整个异步工作流
    """
    logger.info("正在启动取消超时订单的任务...")
    try:
        # 只调用一次 asyncio.run，运行包含所有逻辑的包装器
        result = asyncio.run(_run_task_and_dispose())
        logger.info(f"任务完成： {result}")
        return result
    except Exception as e:
        logger.error(f"运行取消超时订单任务时发生严重错误: {e}", exc_info=True)
        raise
