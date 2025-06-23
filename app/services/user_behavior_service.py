import time
from typing import List

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browsing_history import BrowsingHistory


class UserBehaviorService:
    """
    处理用户行为相关逻辑的服务
    """

    def __init__(self, max_history_size: int = 100):
        """
        初始化服务
        :param max_history_size: 在Redis中为每个用户保留的最大历史记录数
        """
        self.BROWSING_HISTORY_KEY_PREFIX = "browsing_history:user:"
        self.MAX_HISTORY_SIZE = max_history_size

    def _get_history_key(self, user_id: int) -> str:
        """生成用户浏览历史的Redis键"""
        return f"{self.BROWSING_HISTORY_KEY_PREFIX}{user_id}"

    async def add_browsing_history(
            self, db: AsyncSession, redis: Redis, *, user_id: int, sku_id: int
    ) -> None:
        """
        添加一条用户浏览记录.
        采用双写模式：先写入数据库，再写入Redis缓存.
        """
        # 1. 写入数据库以实现持久化
        history_entry = BrowsingHistory(user_id=user_id, sku_id=sku_id)
        db.add(history_entry)
        await db.commit()

        # 2. 写入Redis ZSET以实现快速读取
        history_key = self._get_history_key(user_id)
        timestamp = time.time()

        # 使用ZADD将SKU ID添加到有序集合，分数为当前时间戳
        # 如果SKU已存在，则更新其时间戳
        await redis.zadd(history_key, {str(sku_id): timestamp})

        # 3. 修剪ZSET，只保留最新的N条记录，防止内存无限增长
        # 保留索引从-MAX_HISTORY_SIZE到-1的元素，即最新的N个
        await redis.zremrangebyrank(history_key, 0, -self.MAX_HISTORY_SIZE - 1)

    async def get_recent_browsing_history_sku_ids(
            self, redis: Redis, *, user_id: int, limit: int = 20
    ) -> List[int]:
        """
        从Redis中获取最近的浏览历史SKU ID列表.
        """
        history_key = self._get_history_key(user_id)

        # 使用ZREVRANGE按分数（时间戳）从高到低获取成员
        sku_ids = await redis.zrevrange(history_key, 0, limit - 1)

        return [int(sku_id) for sku_id in sku_ids]


# 创建一个服务实例，以便在其他地方导入和使用
user_behavior_service = UserBehaviorService()
