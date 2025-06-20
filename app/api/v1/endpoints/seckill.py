from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import seckill as seckill_schema
from app.services.seckill_service import seckill_service

router = APIRouter()


# 秒杀活动管理
@router.post(
    "/activities/",
    response_model=seckill_schema.SeckillActivity,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="创建秒杀活动",
)
async def create_seckill_activity(
        activity_in: seckill_schema.SeckillActivityCreate,
        db: AsyncSession = Depends(deps.get_db),
):
    return await seckill_service.create_activity(db=db, activity_in=activity_in)


@router.get(
    "/activities/",
    response_model=List[seckill_schema.SeckillActivity],
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="获取秒杀活动列表",
)
async def read_seckill_activities(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(deps.get_db),
):
    return await seckill_service.get_all_activities(db=db, skip=skip, limit=limit)


@router.get(
    "/activities/{activity_id}",
    response_model=seckill_schema.SeckillActivity,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="获取单个秒杀活动详情",
)
async def read_seckill_activity(
        activity_id: int,
        db: AsyncSession = Depends(deps.get_db),
):
    db_activity = await seckill_service.get_activity(db, activity_id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return db_activity


@router.put(
    "/activities/{activity_id}",
    response_model=seckill_schema.SeckillActivity,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="更新秒杀活动",
)
async def update_seckill_activity(
        activity_id: int,
        activity_in: seckill_schema.SeckillActivityUpdate,
        db: AsyncSession = Depends(deps.get_db),
):
    db_activity = await seckill_service.update_activity(
        db, activity_id=activity_id, activity_in=activity_in
    )
    if db_activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return db_activity


@router.delete(
    "/activities/{activity_id}",
    status_code=204,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="删除秒杀活动",
)
async def delete_seckill_activity(
        activity_id: int,
        db: AsyncSession = Depends(deps.get_db),
):
    success = await seckill_service.delete_activity(db, activity_id=activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activity not found")
    return


@router.post(
    "/activities/{activity_id}/load",
    summary="预热秒杀活动库存到Redis",
    dependencies=[Depends(deps.has_permission("product_manage"))],
)
async def load_activity_to_redis(
        activity_id: int,
        db: AsyncSession = Depends(deps.get_db),
):
    """
    将指定的秒杀活动及其商品库存加载到Redis中进行预热。
    这是一个幂等且原子性的操作。
    """
    await seckill_service.load_activity_to_redis(db, activity_id)
    return {"message": "Activity preloaded successfully"}


# 秒杀商品管理
@router.post(
    "/activities/{activity_id}/products",
    response_model=seckill_schema.SeckillProduct,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="为活动添加秒杀商品",
)
async def add_seckill_product(
        activity_id: int,
        product_in: seckill_schema.SeckillProductCreate,
        db: AsyncSession = Depends(deps.get_db),
):
    return await seckill_service.add_product_to_activity(
        db, activity_id=activity_id, product_in=product_in
    )


@router.put(
    "/products/{product_id}",
    response_model=seckill_schema.SeckillProduct,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="更新秒杀商品信息",
)
async def update_seckill_product(
        product_id: int,
        product_in: seckill_schema.SeckillProductUpdate,
        db: AsyncSession = Depends(deps.get_db),
):
    db_product = await seckill_service.update_product_in_activity(
        db, product_id=product_id, product_in=product_in
    )
    if db_product is None:
        raise HTTPException(status_code=404, detail="Seckill product not found")
    return db_product


@router.delete(
    "/products/{product_id}",
    status_code=204,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="从活动中移除秒杀商品",
)
async def remove_seckill_product(
        product_id: int,
        db: AsyncSession = Depends(deps.get_db),
):
    success = await seckill_service.remove_product_from_activity(
        db, product_id=product_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Seckill product not found")
    return
