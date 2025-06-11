import asyncio
import aio_pika
import json
import logging
from app.utils.email_utils import send_low_stock_email

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("alert_consumer")


async def process_alert(alert_data: dict):
    """处理单条预警消息 - 仅记录日志"""
    log_entry = (
        f"[低库存预警] 库存项ID: {alert_data['inventory_item_id']}, "
        f"当前库存: {alert_data['quantity']}, "
        f"预警阈值: {alert_data['alert_threshold']}, "
        f"可用库存: {alert_data.get('available_quantity', 'N/A')}"
    )
    logger.info(log_entry)

    # 异步发送邮件（不阻塞循环）
    try:
        await send_low_stock_email(alert_data)
        logger.info("已发送邮件通知")
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")


async def consume_alerts():
    """持续消费预警消息"""
    # 使用本地RabbitMQ（默认配置）
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    queue = await channel.declare_queue("low_stock_alerts", durable=True)

    logger.info(f"开始监听低库存预警队列: {queue.name}")

    async for message in queue:
        try:
            alert_data = json.loads(message.body.decode())
            await process_alert(alert_data)
            await message.ack()
        except Exception as e:
            logger.error(f"处理预警失败: {str(e)}")
            await message.nack(requeue=False)


if __name__ == "__main__":
    asyncio.run(consume_alerts())
