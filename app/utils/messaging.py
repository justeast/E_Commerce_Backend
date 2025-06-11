import aio_pika
import json

# RabbitMQ 配置
RABBITMQ_HOST = "localhost"  # RabbitMQ 服务器地址
RABBITMQ_PORT = 5672  # RabbitMQ 服务器端口
RABBITMQ_USER = "guest"  # RabbitMQ 用户名
RABBITMQ_PASS = "guest"  # RabbitMQ 密码
RABBITMQ_QUEUE = "inventory_alerts"  # 库存预警消息队列名称


async def send_alert_to_queue(alert_data: dict):
    """发送预警消息到RabbitMQ队列"""
    try:
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        channel = await connection.channel()

        # 声明持久化队列
        queue = await channel.declare_queue("low_stock_alerts", durable=True)

        # 发送消息
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(alert_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue.name
        )
        await connection.close()
    except Exception as e:
        print(f"发送预警消息失败: {str(e)}")
