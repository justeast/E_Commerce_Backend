import asyncio
import uuid
from redis.asyncio import Redis


class RedisLock:
    """Redis分布式锁实现"""

    def __init__(self, redis_client: Redis, lock_name: str, expire_seconds: int = 10):
        """
        初始化Redis锁
        :param redis_client: Redis客户端
        :param lock_name: 锁名称
        :param expire_seconds: 锁过期时间（秒）
        """
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.expire_seconds = expire_seconds
        self.lock_value = str(uuid.uuid4())  # 锁的唯一值，用于安全释放
        self._locked = False

    async def acquire(self, retry_times: int = 3, retry_delay: float = 0.2) -> bool:
        """
        获取锁
        :param retry_times: 重试次数
        :param retry_delay: 重试延迟（秒）
        :return: bool 是否成功获取锁
        """
        for i in range(retry_times + 1):
            # 尝试获取锁，使用NX选项确保只有在锁不存在时才设置成功
            success = await self.redis.set(
                self.lock_name,
                self.lock_value,
                nx=True,
                ex=self.expire_seconds
            )

            if success:
                self._locked = True
                return True

            if i < retry_times:
                await asyncio.sleep(retry_delay)

        return False

    async def release(self) -> bool:
        """
        释放锁（只有当前持有者才能释放）
        :return: bool 是否成功释放锁
        """
        if not self._locked:
            return False

        # 使用Lua脚本确保原子性操作：只有当锁的值与设置的值相同时才删除
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """

        result = await self.redis.eval(
            script,
            1,  # keys的数量
            self.lock_name,
            self.lock_value
        )

        if result:
            self._locked = False
            return True
        return False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.release()
