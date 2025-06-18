from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import has_permission, get_db
from app.schemas.promotion import Promotion, PromotionCreate, PromotionUpdate
from app.services.promotion_service import promotion_service
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=Promotion, status_code=status.HTTP_201_CREATED,
             summary="创建促销活动", description="创建一个新的促销活动。需要商品管理权限")
async def create_promotion(
        *,
        db: AsyncSession = Depends(get_db),
        promotion_in: PromotionCreate,
        _: User = Depends(has_permission("product_manage")),  # noqa
) -> Any:
    """
    :param db:数据库
    :param promotion_in:促销活动的详细信息
    """
    promotion = await promotion_service.create_promotion(db=db, promotion_in=promotion_in)
    return promotion


@router.get("/", response_model=List[Promotion],
            summary="获取促销活动列表", description="检索所有促销活动，支持分页")
async def read_promotions(
        db: AsyncSession = Depends(get_db),
        skip: int = 0,
        limit: int = 100,
) -> Any:
    """
    :param db: 数据库会话
    :param skip: 分页查询起始位置
    :param limit: 每页数量
    """
    promotions = await promotion_service.get_promotions(db, skip=skip, limit=limit)
    return promotions


@router.get("/{promotion_id}", response_model=Promotion,
            summary="获取指定ID的促销活动", description="根据ID获取单个促销活动的详细信息")
async def read_promotion_by_id(
        promotion_id: int,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    :param promotion_id: 促销活动ID
    :param db: 数据库会话
    """
    promotion = await promotion_service.get_promotion_by_id(db=db, promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的促销活动")
    return promotion


@router.put("/{promotion_id}", response_model=Promotion,
            summary="更新促销活动", description="更新指定ID的促销活动信息。需要商品管理权限")
async def update_promotion(
        *,
        db: AsyncSession = Depends(get_db),
        promotion_id: int,
        promotion_in: PromotionUpdate,
        _: User = Depends(has_permission("product_manage")),  # noqa
) -> Any:
    """
    :param db: 数据库会话
    :param promotion_id: 促销活动ID
    :param promotion_in: 需要更新的字段
    """
    promotion = await promotion_service.get_promotion_by_id(db=db, promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的促销活动")

    updated_promotion = await promotion_service.update_promotion(db=db, promotion=promotion, promotion_in=promotion_in)
    return updated_promotion


@router.delete("/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="删除促销活动", description="根据ID删除一个促销活动。需要商品管理权限")
async def delete_promotion(
        *,
        db: AsyncSession = Depends(get_db),
        promotion_id: int,
        _: User = Depends(has_permission("product_manage")),  # noqa
) -> None:
    """
    :param db: 数据库会话
    :param promotion_id: 促销活动ID
    """
    promotion = await promotion_service.get_promotion_by_id(db=db, promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的促销活动")

    await promotion_service.delete_promotion(db=db, promotion_id=promotion_id)
    return None
