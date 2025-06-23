from redis.asyncio import Redis

# Redis配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = "123456"

# Redis连接字符串
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


async def get_redis_pool() -> Redis:
    """
    创建并返回一个新的 Redis 客户端实例（由于担心多处调用修改的问题，所以函数名并没有修改）
    这确保了每个异步任务都能获得自己的客户端，从而防止事件循环冲突
    """
    return Redis.from_url(
        REDIS_URL,
        password=REDIS_PASSWORD,
        encoding="utf-8",
        decode_responses=True
    )
