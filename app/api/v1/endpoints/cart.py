from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cart import Cart, CartItemCreate, CartItemUpdate
from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.services.cart_service import cart_service

router = APIRouter()


@router.get("/", response_model=Cart)
async def read_user_cart(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的购物车"""
    cart = await cart_service.get_user_cart(db, user=current_user)
    return cart


@router.post("/items", response_model=Cart)
async def add_item_to_cart(
        *,
        db: AsyncSession = Depends(get_db),
        item_in: CartItemCreate,
        current_user: User = Depends(get_current_active_user),
):
    """向购物车中添加商品"""
    try:
        cart = await cart_service.add_item_to_cart(db, user=current_user, item_in=item_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return cart


@router.put("/items/{item_id}", response_model=Cart)
async def update_cart_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_id: int,
        item_in: CartItemUpdate,
        current_user: User = Depends(get_current_active_user),
):
    """更新购物车中商品的数量"""
    try:
        cart = await cart_service.update_cart_item_quantity(db, user=current_user, cart_item_id=item_id,
                                                            item_in=item_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到购物车项目")
    return cart


@router.delete("/items/{item_id}", response_model=Cart)
async def remove_cart_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_id: int,
        current_user: User = Depends(get_current_active_user),
):
    """从购物车中移除商品"""
    cart = await cart_service.remove_cart_item(db, user=current_user, cart_item_id=item_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到购物车项目")
    return cart


@router.delete("/", response_model=Cart, status_code=status.HTTP_200_OK)
async def clear_user_cart(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """清空当前用户的购物车"""
    cart = await cart_service.clear_cart(db, user=current_user)
    return cart
