import asyncio
from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.session import async_session
from app.models.order import Order, OrderStatusEnum
from app.services.order_service import order_service

# 使用 Celery 的标准日志记录器
logger = get_task_logger(__name__)

# 订单超时时间
ORDER_OVERDUE_MINUTES = 5  # 测试


async def _run_cancel_overdue_orders():
    """
    核心异步逻辑：执行取消订单的业务逻辑，并在之后清理资源
    """
    logger.info("正在执行取消超时订单的核心异步逻辑...")
    session: AsyncSession = async_session()

    try:
        timeout_period = timedelta(minutes=ORDER_OVERDUE_MINUTES)
        time_threshold = datetime.now(timezone.utc) - timeout_period

        stmt = select(Order.order_sn).where(
            Order.status == OrderStatusEnum.PENDING_PAYMENT,
            Order.created_at < time_threshold
        )
        result = await session.execute(stmt)
        overdue_order_sns = result.scalars().all()

        total_count = len(overdue_order_sns)
        if total_count == 0:
            logger.info("没有找到需要取消的超时订单。")
            return "没有找到需要取消的超时订单。"

        logger.info(f"发现 {total_count} 个超时订单，准备取消...")

        cancelled_count = 0
        for order_sn in overdue_order_sns:
            try:
                await order_service.cancel_order(
                    db=session,
                    order_sn=order_sn,
                )
                cancelled_count += 1
            except Exception as e:
                logger.error(f"取消订单 {order_sn} 时失败: {e}", exc_info=True)

        await session.commit()
        logger.info(f"成功取消 {cancelled_count}/{total_count} 个订单")
        return f"成功取消 {cancelled_count}/{total_count} 个订单"

    except Exception:
        await session.rollback()
        logger.error("执行取消超时订单核心逻辑时发生异常，已回滚。", exc_info=True)
        raise
    finally:
        await session.close()


@celery_app.task
def cancel_overdue_orders_task():
    """
    同步的 Celery 任务，用于取消超时订单
    """
    logger.info("正在启动取消超时订单的任务...")
    try:
        result = asyncio.run(_run_cancel_overdue_orders())
        logger.info(f"任务完成： {result}")
        return result
    except Exception as e:
        # 异常已在异步函数中记录，这里只需重新抛出给Celery
        raise
