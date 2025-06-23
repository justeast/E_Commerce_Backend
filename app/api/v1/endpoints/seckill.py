from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import seckill as seckill_schema
from app.services.seckill_service import seckill_service
from app.models.user import User

router = APIRouter()


# ---Admin endpoints---

# 秒杀活动管理
@router.post(
    "/activities/",
    response_model=seckill_schema.SeckillActivity,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="创建秒杀活动",
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
)
async def load_activity_to_redis(
        activity_id: int,
        db: AsyncSession = Depends(deps.get_db),
):
    """
    将指定的秒杀活动及其商品库存加载到Redis中进行预热
    这是一个幂等且原子性的操作
    """
    await seckill_service.load_activity_to_redis(db, activity_id)
    return {"message": "Activity preloaded successfully"}


# 秒杀商品管理
@router.post(
    "/activities/{activity_id}/products",
    response_model=seckill_schema.SeckillProduct,
    dependencies=[Depends(deps.has_permission("product_manage"))],
    summary="为活动添加秒杀商品",
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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
    tags=["Admin Seckill Management"],
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


# --- Public Endpoints ---

@router.get(
    "/public/activities/",
    response_model=List[seckill_schema.SeckillActivityPublic],
    summary="获取公开的秒杀活动列表",
    tags=["Public Seckill"],
)
async def read_public_seckill_activities(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(deps.get_db),
        _: User = Depends(deps.get_current_active_user),
):
    """
    获取所有对用户可见的秒杀活动列表
    - 只返回状态为 `PENDING` (未开始) 和 `ACTIVE` (进行中) 的活动
    - 列表不包含详细的商品信息
    """
    activities = await seckill_service.get_public_activities(db=db, skip=skip, limit=limit)
    return activities


@router.get(
    "/public/activities/{activity_id}",
    response_model=seckill_schema.SeckillActivity,
    summary="获取单个公开的秒杀活动详情",
    tags=["Public Seckill"],
)
async def read_public_seckill_activity(
        activity_id: int,
        db: AsyncSession = Depends(deps.get_db),
        _: User = Depends(deps.get_current_active_user),
):
    """
    获取单个秒杀活动的详细信息，包括关联的秒杀商品
    - 只返回状态为 `PENDING` (未开始) 和 `ACTIVE` (进行中) 的活动
    """
    db_activity = await seckill_service.get_public_activity(db, activity_id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=404, detail="Activity not found or not available")
    return db_activity


# 秒杀下单
@router.post(
    "/activities/{activity_id}/orders/",
    response_model=seckill_schema.SeckillOrderResponse,
    status_code=202,  # Accepted
    summary="创建秒杀订单",
    tags=["Public Seckill"],
)
async def create_seckill_order(
        activity_id: int,
        order_in: seckill_schema.SeckillOrderCreate,
        current_user: User = Depends(deps.get_current_active_user),
):
    """
    处理用户的秒杀请求
    - 前置检查: 活动有效性、库存、用户限购等 (由Redis Lua脚本原子性执行)
    - 异步处理: 如果校验通过，请求将被接受并放入消息队列中异步处理
    - 即时响应: 立即返回一个唯一的 `request_id`，用于后续查询订单处理状态
    """
    try:
        response = await seckill_service.create_seckill_order(
            activity_id=activity_id, user_id=current_user.id, order_in=order_in
        )
        return response

    except ValueError as e:
        # 捕获服务层抛出的业务逻辑异常，并以400状态码返回
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/public/orders/status/{request_id}",
    response_model=seckill_schema.SeckillOrderStatus,
    summary="查询秒杀订单处理状态",
    tags=["Public Seckill"],
)
async def get_seckill_order_status(
        request_id: str,
        current_user: User = Depends(deps.get_current_active_user),
):
    """
    根据创建秒杀订单时返回的 `request_id`，前端可以轮询此端点以获取订单的最终处理结果
    """
    status = await seckill_service.get_seckill_order_status(
        request_id=request_id, user_id=current_user.id
    )
    if status is None:
        raise HTTPException(status_code=404, detail="请求不存在或已过期。")
    return status
