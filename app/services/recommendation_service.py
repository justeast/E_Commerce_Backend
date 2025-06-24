import math
import itertools
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browsing_history import BrowsingHistory


class RecommendationService:
    """
    离线协同过滤推荐
    """

    async def collect_user_histories(  # noqa
            self, db: AsyncSession, days: int
    ) -> Dict[int, List[int]]:
        """
        返回 {user_id: [sku_id1, sku_id2, ...]}；列表去重
        """
        since_time = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(
            BrowsingHistory.user_id, BrowsingHistory.sku_id
        ).where(BrowsingHistory.browsed_at >= since_time)
        result = await db.execute(stmt)
        user_sku: Dict[int, set] = defaultdict(set)
        for user_id, sku_id in result:
            user_sku[user_id].add(sku_id)
        # 转为 list
        return {u: list(skus) for u, skus in user_sku.items() if len(skus) > 1}

    def build_cooccurrence(  # noqa
            self, user_histories: Dict[int, List[int]]
    ) -> Tuple[Dict[Tuple[int, int], int], Dict[int, int]]:
        """
        统计共现次数及每个 sku 的出现次数
        """
        co_counts: Dict[Tuple[int, int], int] = defaultdict(int)
        sku_freq: Dict[int, int] = defaultdict(int)
        for skus in user_histories.values():
            for sku in skus:
                sku_freq[sku] += 1
            for i, j in itertools.combinations(sorted(skus), 2):
                co_counts[(i, j)] += 1
        return co_counts, sku_freq

    def calculate_similarity(  # noqa
            self,
            co_counts: Dict[Tuple[int, int], int],
            sku_freq: Dict[int, int],
    ) -> Dict[int, Dict[int, float]]:
        """
        余弦相似度  sim(i,j) = co_cnt / sqrt(freq_i * freq_j)
        返回 {sku_i: {sku_j: score}}
        """
        similarity: Dict[int, Dict[int, float]] = defaultdict(dict)
        for (i, j), c in co_counts.items():
            score = c / math.sqrt(sku_freq[i] * sku_freq[j])
            similarity[i][j] = score
            similarity[j][i] = score
        return similarity

    async def cache_similar_items(  # noqa
            self, redis: Redis, similarity: Dict[int, Dict[int, float]], top_k: int
    ):
        """
        为每个 sku 写 Redis ZSET，保留 Top-K
        """
        pipe = redis.pipeline()
        for sku_id, sim_dict in similarity.items():
            key = f"item_sim:{sku_id}"
            # 取 Top-K
            top_items = sorted(
                sim_dict.items(), key=lambda x: x[1], reverse=True
            )[:top_k]
            if top_items:
                # 先删除旧值
                pipe.delete(key)
                pipe.zadd(key, {str(sim_id): score for sim_id, score in top_items})
        await pipe.execute()

    async def generate_item_similarity(
            self,
            db: AsyncSession,
            redis: Redis,
            days: int = 30,
            top_k: int = 20,
    ):
        """
        整体流程入口
        """
        histories = await self.collect_user_histories(db, days=days)
        if not histories:
            return  # 数据不足
        co_counts, sku_freq = self.build_cooccurrence(histories)
        similarity = self.calculate_similarity(co_counts, sku_freq)
        await self.cache_similar_items(redis, similarity, top_k)

    async def get_similar_skus(  # noqa
            self, redis: Redis, sku_id: int, limit: int = 20
    ) -> List[int]:
        """
        从 Redis ZSET 取出 sku_id 的相似 SKU 列表
        """
        key = f"item_sim:{sku_id}"
        sim_ids = await redis.zrevrange(key, 0, limit - 1)
        return [int(i) for i in sim_ids]


# 单例
recommendation_service = RecommendationService()
