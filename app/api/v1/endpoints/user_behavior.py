from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.redis_client import get_redis_pool
from app.models.browsing_history import BrowsingHistory
from app.models.product_attribute import SKU
from app.models.user import User
from app.schemas.browsing_history import BrowsingHistoryRead
from app.services.user_behavior_service import user_behavior_service

router = APIRouter()


@router.post(
    "/history/{sku_id}",
    summary="记录浏览历史",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def record_browsing_history(
        sku_id: int,
        db: AsyncSession = Depends(deps.get_db),
        redis: Redis = Depends(get_redis_pool),
        current_user: User = Depends(deps.get_current_active_user),
):
    """
    记录当前登录用户对指定SKU的浏览历史.
    """
    sku = await db.get(SKU, sku_id)
    if not sku:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found")

    await user_behavior_service.add_browsing_history(
        db=db, redis=redis, user_id=current_user.id, sku_id=sku_id
    )
    return


@router.get(
    "/history/",
    summary="获取最近浏览历史",
    response_model=List[BrowsingHistoryRead],
)
async def get_recent_browsing_history(
        db: AsyncSession = Depends(deps.get_db),
        redis: Redis = Depends(get_redis_pool),
        current_user: User = Depends(deps.get_current_active_user),
        limit: int = 20,
):
    """
    获取当前登录用户最近的浏览历史记录.
    """
    # 1. 从Redis获取最近浏览的SKU ID列表，这保证了响应顺序是最新的
    sku_ids = await user_behavior_service.get_recent_browsing_history_sku_ids(
        redis=redis, user_id=current_user.id, limit=limit
    )

    if not sku_ids:
        return []

    # 2. 从数据库批量查询这些 BrowsingHistory 记录
    #    并预加载 SKU 及其关联的属性，以避免 N+1 查询
    query = (
        select(BrowsingHistory)
        .where(BrowsingHistory.user_id == current_user.id, BrowsingHistory.sku_id.in_(sku_ids))
        .options(
            selectinload(BrowsingHistory.sku).selectinload(SKU.attribute_values)
        )
    )
    result = await db.execute(query)
    histories = result.scalars().all()

    # 3. 按Redis返回的顺序（最新在前）重新排序从数据库查出的记录
    history_map = {history.sku_id: history for history in histories}
    ordered_histories = [history_map[sku_id] for sku_id in sku_ids if sku_id in history_map]

    return ordered_histories
