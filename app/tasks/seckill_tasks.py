import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import json

from celery.utils.log import get_task_logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import get_redis_pool
from app.db.session import async_session
from app.models.order import Order, OrderItem, OrderStatusEnum
from app.models.product_attribute import SKU
from app.models.seckill import SeckillActivity, SeckillActivityStatus, SeckillProduct
from app.services.inventory_service import inventory_service
from app.utils.redis_lock import RedisLock

logger = get_task_logger(__name__)


async def _run_update_seckill_status():
    """
    核心异步逻辑：更新秒杀活动状态，并在之后清理资源
    """
    logger.info("开始执行秒杀活动状态更新任务的核心异步逻辑...")
    session: AsyncSession = async_session()
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

    except Exception as e:
        logger.error(f"运行秒杀活动状态更新任务时发生严重错误: {e}", exc_info=True)
        raise
    finally:
        await session.close()


@celery_app.task
def update_seckill_activity_status_task():
    """
    同步的 Celery 任务，用于更新秒杀活动状态
    """
    logger.info("启动秒杀活动状态更新任务...")
    try:
        result = asyncio.run(_run_update_seckill_status())
        logger.info(f"任务完成: {result}")
        return result
    except Exception as e:
        # 异常已在异步函数中记录，这里只需重新抛出给Celery
        raise


# --- 秒杀订单创建任务 ---

COMPENSATE_REDIS_LUA = """
-- KEYS[1]: stock_key (seckill:stock:{product_id})
-- KEYS[2]: user_purchase_key (seckill:purchase:user:{user_id}:activity:{activity_id})
-- ARGV[1]: product_id
-- ARGV[2]: quantity

-- 1. Restore stock
redis.call('INCRBY', KEYS[1], ARGV[2])

-- 2. Decrement user purchase count if it exists
local current_purchased = redis.call('HGET', KEYS[2], ARGV[1])
if current_purchased then
    redis.call('HINCRBY', KEYS[2], ARGV[1], -tonumber(ARGV[2]))
end

return 1
"""


async def _update_request_status_on_failure(request_id: str, reason: str, user_id: int):
    """异步辅助函数，用于在任务最终失败时更新Redis状态"""
    redis = await get_redis_pool()
    try:
        status_key = f"seckill:request:{request_id}"
        failure_status = {
            "status": "FAILED",
            "message": f"订单处理失败: {reason}",
            "user_id": user_id
        }
        await redis.set(status_key, json.dumps(failure_status), ex=600)
        logger.info(f"已将请求 {request_id} 的状态更新为 FAILED。")
    except Exception as e:
        logger.error(f"更新请求 {request_id} 状态为 FAILED 时发生错误: {e}", exc_info=True)
    finally:
        await redis.close()


async def _run_create_seckill_order(task_body: dict):
    """
    核心异步逻辑：从任务消息创建秒杀订单，并在之后清理资源
    """
    logger.info(f"开始处理秒杀订单任务的核心异步逻辑: {task_body}")
    session: AsyncSession = async_session()
    redis = await get_redis_pool()

    # 从任务体中提取数据
    request_id = task_body['request_id']
    user_id = task_body['user_id']
    seckill_product_id = task_body['seckill_product_id']
    seckill_price = Decimal(str(task_body['price']))
    order_details = task_body['order_details']
    sku_id = order_details['sku_id']
    quantity = order_details['quantity']

    lock = RedisLock(redis, f"inventory:sku:{sku_id}", expire_seconds=15)
    if not await lock.acquire():
        logger.warning(f"获取SKU {sku_id} 的锁失败，任务将重试。")
        raise Exception(f"Could not acquire lock for SKU {sku_id}")

    seckill_product = None
    try:
        seckill_product = await session.get(
            SeckillProduct,
            seckill_product_id,
            options=[selectinload(SeckillProduct.sku).selectinload(SKU.product)]
        )
        if not seckill_product or not seckill_product.sku or not seckill_product.sku.product:
            logger.critical(f"数据不一致：在创建订单时找不到秒杀商品 {seckill_product_id}。Redis预扣减可能需要手动恢复。")
            raise ValueError(f"无法找到秒杀商品 {seckill_product_id} 或其关联的SKU/产品信息。")

        async with session.begin_nested():
            order_sn = f"SKSN{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"

            await inventory_service.reserve_stock(
                db=session,
                sku_id=sku_id,
                quantity=quantity,
                reference_id=order_sn,
                reference_type="seckill_order_creation",
                operator_id=user_id,
                notes=f"秒杀订单 {order_sn} 预留库存"
            )

            total_amount = seckill_price * quantity
            order_item = OrderItem(
                sku_id=sku_id,
                product_name=seckill_product.sku.product.name,
                sku_name=seckill_product.sku.name,
                sku_price=seckill_price,
                quantity=quantity,
                sku_image_url=seckill_product.sku.image_url,
            )
            new_order = Order(
                order_sn=order_sn,
                user_id=user_id,
                total_amount=total_amount,
                pay_amount=total_amount,
                status=OrderStatusEnum.PENDING_PAYMENT,
                receiver_name=order_details['receiver_name'],
                receiver_phone=order_details['receiver_phone'],
                receiver_address=order_details['receiver_address'],
                notes=order_details.get('notes'),
                items=[order_item]
            )
            session.add(new_order)

        await session.commit()
        logger.info(f"秒杀订单 {order_sn} 已成功创建。")

        # 更新Redis中的请求状态为成功
        status_key = f"seckill:request:{request_id}"
        success_status = {
            "status": "SUCCESS",
            "message": "订单创建成功",
            "order_id": new_order.id,
            "order_sn": new_order.order_sn,
            "user_id": user_id
        }
        await redis.set(status_key, json.dumps(success_status), ex=600)
        logger.info(f"已将请求 {request_id} 的状态更新为 SUCCESS。")

    except Exception as e:
        logger.error(f"处理秒杀订单任务失败，将尝试补偿并重试: {e}", exc_info=True)
        await session.rollback()

        if seckill_product:
            try:
                activity_id = seckill_product.activity_id
                stock_key = f"seckill:stock:{seckill_product_id}"
                user_purchase_key = f"seckill:purchase:user:{user_id}:activity:{activity_id}"

                await redis.eval(
                    COMPENSATE_REDIS_LUA,
                    2,
                    stock_key,
                    user_purchase_key,
                    seckill_product_id,
                    quantity
                )
                logger.info(f"Redis 补偿成功: 为秒杀商品 {seckill_product_id} 恢复了 {quantity} 个库存。")
            except Exception as comp_exc:
                logger.critical(f"Redis 补偿失败! 需要手动干预. Error: {comp_exc}", exc_info=True)
        else:
            logger.error("无法执行 Redis 补偿，因为秒杀商品信息在任务开始时未能获取。")

        raise e

    finally:
        await lock.release()
        await session.close()
        await redis.close()


@celery_app.task(
    name=settings.CELERY_TASK_CREATE_SECKILL_ORDER,
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5}
)
def create_seckill_order_task(self, task_body: dict):
    """
    同步的 Celery 任务，用于异步创建秒杀订单
    """
    logger.info(f"接收到秒杀订单创建任务: {task_body}")
    try:
        asyncio.run(_run_create_seckill_order(task_body))
    except Exception as e:
        logger.warning(f"任务执行失败，准备重试或标记为最终失败。错误: {e}")
        # 检查是否是最后一次重试
        if self.request.retries >= self.max_retries:
            logger.error(f"任务 {self.request.id} 已达到最大重试次数，将标记为最终失败。")
            request_id = task_body.get("request_id")
            user_id = task_body.get("user_id")
            if request_id and user_id:
                asyncio.run(_update_request_status_on_failure(request_id, str(e), user_id))
        raise e
