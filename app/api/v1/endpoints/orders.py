from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.models.order import OrderStatusEnum
from app.models.user import User
from app.schemas.order import Order, OrderCreate, OrderCreateFromSelected
from app.services.order_service import order_service
from app.services.payment_service import alipay_service

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


@router.get("/{order_sn}", response_model=Order)
async def get_order_details(
        order_sn: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    获取单个订单的详细信息
    """
    try:
        order = await order_service.get_order_by_sn(db=db, order_sn=order_sn, user_id=current_user.id)
        return order
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# 定义支付URL的响应模型
class PaymentURLResponse(BaseModel):
    payment_url: str


@router.post("/{order_sn}/pay", response_model=PaymentURLResponse)
async def request_payment_for_order(
        order_sn: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    为指定订单请求支付，返回支付宝支付URL
    路径参数使用 order_sn 以便用户友好
    """
    try:
        # 1. 获取订单，并验证用户权限
        order = await order_service.get_order_by_sn(db=db, order_sn=order_sn, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # 2. 检查订单状态是否为“待支付”
    if order.status != OrderStatusEnum.PENDING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订单 {order_sn} 状态为 {order.status.value}，不能发起支付。"
        )

    # 3. 准备支付参数
    subject = f"订单 {order.order_sn} - {order.items[0].product_name if order.items else '商品合集'}"
    if len(order.items) > 1:
        subject += " 等"

    total_amount = float(order.pay_amount)  # 确保金额是浮点数

    # 4. 调用支付宝服务生成支付URL
    try:
        payment_url = alipay_service.create_pc_payment_url(
            order_sn=order.order_sn,
            total_amount=total_amount,
            subject=subject
        )
        return PaymentURLResponse(payment_url=payment_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成支付链接失败: {str(e)}"
        )


@router.post("/{order_sn}/cancel", response_model=Order)
async def cancel_order(
        order_sn: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    用户主动取消一个“待支付”的订单
    """
    try:
        # 调用服务层方法来执行取消逻辑
        cancelled_order = await order_service.cancel_order(db=db, order_sn=order_sn, user=current_user)
        await db.commit()
        return cancelled_order
    except ValueError as e:
        await db.rollback()
        # 服务层会抛出ValueError，例如订单不存在、状态不正确等
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        # 兜底的异常处理
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"取消订单时发生内部错误: {str(e)}")
