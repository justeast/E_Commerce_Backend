from pydantic import BaseModel, ConfigDict, field_validator, Field
from datetime import datetime
from typing import List, Optional
import re

from app.schemas.product_attribute import SKU


#  OrderItem Schemas

class OrderItemBase(BaseModel):
    sku_id: int
    quantity: int
    price: float = Field(validation_alias='sku_price')


class OrderItem(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: SKU


# Order Schemas

class OrderBase(BaseModel):
    total_amount: float
    status: str = 'pending_payment'


class Order(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_sn: str
    user_id: int
    pay_amount: float
    receiver_name: str
    receiver_phone: str
    receiver_address: str
    notes: Optional[str] = None
    created_at: datetime
    items: List[OrderItem] = []


class OrderCreate(BaseModel):
    """用于创建订单的输入模型"""
    receiver_name: str
    receiver_phone: str
    receiver_address: str
    notes: Optional[str] = None

    @field_validator('receiver_phone')
    @classmethod
    def validate_phone_number(cls, v):
        """验证手机号码是否合法"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('无效的手机号码格式')
        return v


class OrderCreateFromSelected(OrderCreate):
    """用于从购物车中选择部分商品创建订单的输入模型"""
    selected_cart_item_ids: List[int] = Field(..., min_length=1)
