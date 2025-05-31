from redis.asyncio import Redis
from typing import Optional

# Redis配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = "123456"

# Redis连接字符串
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Redis连接池
redis_pool: Optional[Redis] = None


async def get_redis_pool() -> Redis:
    """
    获取Redis连接池
    """
    global redis_pool
    if redis_pool is None:
        # 创建Redis连接池
        redis_pool = Redis.from_url(
            REDIS_URL,
            password=REDIS_PASSWORD,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_pool
