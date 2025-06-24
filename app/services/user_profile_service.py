from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browsing_history import BrowsingHistory
from app.models.product_attribute import SKU
from app.models.product import Product
from app.models.user_profile import UserProfileTag


class UserProfileService:
    async def aggregate_and_upsert_tags(  # noqa
            self,
            db: AsyncSession,
            days: int = 30,
            top_n_categories: int = 3,
    ) -> None:
        """根据最近 *days* 天的行为数据生成 / 更新用户画像标签。

        目前实现两个维度：
        1. interest_category  —— 浏览次数 Top-N 的商品一级分类
        2. activity_level     —— 浏览事件总数映射到 low/medium/high
        """

        # 1. 拉取近 N 天浏览记录
        since_time = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(BrowsingHistory.user_id, BrowsingHistory.sku_id).where(
            BrowsingHistory.browsed_at >= since_time
        )
        result = await db.execute(stmt)
        rows = result.all()
        if not rows:
            return  # 无数据可聚合

        user_skus: Dict[int, List[int]] = defaultdict(list)
        for user_id, sku_id in rows:
            user_skus[user_id].append(sku_id)

        # 2. 构建 SKU → Category 映射（一次批量查询）
        unique_skus = {sku for skus in user_skus.values() for sku in skus}
        sku_category_map: Dict[int, int] = {}
        if unique_skus:
            stmt = (
                select(SKU.id, Product.category_id)
                .join(Product, SKU.product_id == Product.id)
                .where(SKU.id.in_(unique_skus))
            )
            res = await db.execute(stmt)
            sku_category_map = {sid: cid for sid, cid in res}

        # 3. 查询已有画像，便于 UPSERT
        user_ids = list(user_skus.keys())
        stmt = select(UserProfileTag).where(UserProfileTag.user_id.in_(user_ids))
        res = await db.execute(stmt)
        existing_tags: List[UserProfileTag] = res.scalars().all()
        tag_index: Dict[Tuple[int, str, str], UserProfileTag] = {
            (t.user_id, t.tag_key, t.tag_value): t for t in existing_tags
        }

        # 4. 生成标签并 UPSERT
        now = datetime.now(timezone.utc)
        for user_id, skus in user_skus.items():
            # 4.1 兴趣分类 - 浏览次数 Top-N
            cat_counter: Counter[int] = Counter(
                sku_category_map.get(sku) for sku in skus if sku_category_map.get(sku) is not None
            )
            for cat_id, freq in cat_counter.most_common(top_n_categories):
                key = (user_id, "interest_category", str(cat_id))
                if key in tag_index:
                    tag_index[key].weight = float(freq)
                    tag_index[key].updated_at = now
                else:
                    db.add(
                        UserProfileTag(
                            user_id=user_id,
                            tag_key="interest_category",
                            tag_value=str(cat_id),
                            weight=float(freq),
                        )
                    )

            # 4.2 活跃度 - 浏览总数映射等级
            view_cnt = len(skus)
            if view_cnt <= 5:
                level = "low"
            elif view_cnt <= 20:
                level = "medium"
            else:
                level = "high"
            key = (user_id, "activity_level", level)
            if key in tag_index:
                tag_index[key].weight = float(view_cnt)
                tag_index[key].updated_at = now
            else:
                db.add(
                    UserProfileTag(
                        user_id=user_id,
                        tag_key="activity_level",
                        tag_value=level,
                        weight=float(view_cnt),
                    )
                )

        # 5. 提交事务
        await db.commit()

    async def get_user_tags(  # noqa
            self,
            db: AsyncSession,
            user_id: int,
            tag_key: str | None = None,
            limit: int | None = None,
    ) -> List[UserProfileTag]:
        """按权重/更新时间降序返回用户画像标签"""
        stmt = select(UserProfileTag).where(UserProfileTag.user_id == user_id)
        if tag_key:
            stmt = stmt.where(UserProfileTag.tag_key == tag_key)
        stmt = stmt.order_by(UserProfileTag.weight.desc(), UserProfileTag.updated_at.desc())
        if limit:
            stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()


# 单例
user_profile_service = UserProfileService()
