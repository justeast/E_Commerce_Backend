from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas.order import Order, OrderCreate, OrderCreateFromSelected
from app.services.order_service import order_service

router = APIRouter()


@router.post("/", response_model=Order, status_code=status.HTTP_201_CREATED)
async def create_order(
        *,
        db: AsyncSession = Depends(get_db),
        order_in: OrderCreate,
        current_user: User = Depends(get_current_active_user),
):
    """
    从购物车创建新订单
    """
    try:
        order = await order_service.create_order_from_cart(db=db, user=current_user, order_in=order_in)
        return order
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/from-selected-items/", response_model=Order, status_code=status.HTTP_201_CREATED)
async def create_order_from_selected_items(
        *,
        db: AsyncSession = Depends(get_db),
        order_in: OrderCreateFromSelected,
        current_user: User = Depends(get_current_active_user),
):
    """
    从购物车中选择指定商品创建新订单
    """
    try:
        order = await order_service.create_order_from_selected_cart_items(
            db=db,
            user=current_user,
            order_in=order_in
        )
        return order
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # 通用的异常捕获，以防服务层抛出其他类型的错误
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"创建订单时发生内部错误: {str(e)}")
