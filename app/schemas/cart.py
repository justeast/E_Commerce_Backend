from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.schemas.product_attribute import SKU


# Cart Item Schemas
class CartItemBase(BaseModel):
    sku_id: int = Field(..., description="SKU ID")
    quantity: int = Field(..., gt=0, description="Quantity")


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0, description="Quantity")


class CartItem(CartItemBase):
    id: int
    price: float = Field(..., description="Price at the time of adding to cart")
    created_at: datetime
    updated_at: datetime
    sku: SKU

    class Config:
        from_attributes = True


# Cart Schemas
class CartBase(BaseModel):
    user_id: int


class Cart(CartBase):
    id: int
    items: List[CartItem] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
