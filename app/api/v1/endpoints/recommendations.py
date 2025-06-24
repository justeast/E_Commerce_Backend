from typing import List, Dict
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.redis_client import get_redis_pool
from app.models.product_attribute import SKU
from app.models.product import Product
from app.models.order import OrderItem
from app.schemas.product_attribute import SKU as SKUSchema
from app.services.recommendation_service import recommendation_service
from app.services.user_behavior_service import user_behavior_service
from app.services.user_profile_service import user_profile_service

router = APIRouter()


# ------- 基于商品的推荐 -------
@router.get(
    "/item/{sku_id}",
    response_model=List[SKUSchema],
    summary="基于商品的相似商品推荐",
)
async def recommend_for_item(
        sku_id: int,
        db: AsyncSession = Depends(deps.get_db),
        redis: Redis = Depends(get_redis_pool),
        limit: int = 20,
):
    # 校验 SKU 是否存在
    sku = await db.get(SKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    # 从 Redis 读取相似 SKU 列表
    similar_ids = await recommendation_service.get_similar_skus(
        redis=redis, sku_id=sku_id, limit=limit
    )
    if not similar_ids:
        return []

    stmt = (
        select(SKU)
        .where(SKU.id.in_(similar_ids))
        .options(selectinload(SKU.attribute_values))
    )
    result = await db.execute(stmt)
    skus = result.scalars().all()

    # 保持与 Redis 顺序一致
    sku_map: Dict[int, SKU] = {s.id: s for s in skus}
    ordered_skus = [sku_map[sid] for sid in similar_ids if sid in sku_map]
    return ordered_skus


# ------- 基于用户的推荐 -------
@router.get(
    "/user/",
    response_model=List[SKUSchema],
    summary="基于用户最近浏览的推荐",
)
async def recommend_for_user(
        db: AsyncSession = Depends(deps.get_db),
        redis: Redis = Depends(get_redis_pool),
        current_user=Depends(deps.get_current_active_user),
        history_limit: int = 20,
        recommend_limit: int = 20,
):
    # 获取用户最近浏览过的 SKU
    recent_ids = await user_behavior_service.get_recent_browsing_history_sku_ids(
        redis=redis, user_id=current_user.id, limit=history_limit
    )
    if not recent_ids:
        # 如果没有最近浏览记录(即完全冷启动用户)，推荐热销商品
        stmt_hot = (
            select(SKU)
            .join(OrderItem, OrderItem.sku_id == SKU.id)
            .group_by(SKU.id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .options(selectinload(SKU.attribute_values))
            .limit(recommend_limit)
        )
        result = await db.execute(stmt_hot)
        hot_skus = result.scalars().all()
        return hot_skus

    # 聚合相似度（简单加权：按相似列表排名反向加分）
    score_map: defaultdict[int, float] = defaultdict(float)
    for src_id in recent_ids:
        sim_ids = await recommendation_service.get_similar_skus(
            redis=redis, sku_id=src_id, limit=history_limit
        )
        for rank, sim_id in enumerate(sim_ids):
            score_map[sim_id] += (history_limit - rank)

    # 去掉已浏览的
    for sid in recent_ids:
        score_map.pop(sid, None)

    if not score_map:
        score_map = {}

    # 如果协同过滤不足，使用画像兴趣分类兜底
    exclude_ids = set(recent_ids)
    # 排序并截取已有
    top_ids: List[int] = [sid for sid, _ in sorted(
        score_map.items(), key=lambda kv: kv[1], reverse=True
    )[:recommend_limit]]

    if len(top_ids) < recommend_limit:
        need = recommend_limit - len(top_ids)
        tags = await user_profile_service.get_user_tags(
            db=db, user_id=current_user.id, tag_key="interest_category", limit=3
        )
        if tags:
            cat_ids = [int(t.tag_value) for t in tags]
            stmt_cat = (
                select(SKU.id)
                .join(Product, SKU.product_id == Product.id)
                .where(
                    Product.category_id.in_(cat_ids),
                    SKU.id.not_in(exclude_ids.union(top_ids))
                )
                .limit(need)
            )
            extra = await db.execute(stmt_cat)
            extra_ids = [row[0] for row in extra]
            top_ids.extend(extra_ids)

    stmt = (
        select(SKU)
        .where(SKU.id.in_(top_ids))
        .options(selectinload(SKU.attribute_values))
    )
    result = await db.execute(stmt)
    skus = result.scalars().all()
    sku_map = {s.id: s for s in skus}
    ordered = [sku_map[sid] for sid in top_ids if sid in sku_map]
    return ordered
