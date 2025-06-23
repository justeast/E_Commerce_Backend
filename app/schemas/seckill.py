from datetime import datetime
from typing import List, Optional
import re

from pydantic import BaseModel, Field, field_validator

from app.models.seckill import SeckillActivityStatus


# --- SeckillProduct Schemas ---

class SeckillProductBase(BaseModel):
    sku_id: int = Field(..., description="商品SKU ID")
    seckill_price: float = Field(..., gt=0, description="秒杀价")
    seckill_stock: int = Field(..., gt=0, description="秒杀库存")
    purchase_limit: int = Field(default=1, gt=0, description="每人限购数量")


class SeckillProductCreate(SeckillProductBase):
    pass


class SeckillProductUpdate(BaseModel):
    seckill_price: Optional[float] = Field(None, gt=0, description="秒杀价")
    seckill_stock: Optional[int] = Field(None, gt=0, description="秒杀库存")
    purchase_limit: Optional[int] = Field(None, gt=0, description="每人限购数量")


class SeckillProduct(SeckillProductBase):
    id: int
    activity_id: int

    class Config:
        from_attributes = True


# --- SeckillActivity Schemas ---

class SeckillActivityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="活动名称")
    description: Optional[str] = Field(None, max_length=255, description="活动描述")
    start_time: datetime = Field(..., description="秒杀开始时间")
    end_time: datetime = Field(..., description="秒杀结束时间")


class SeckillActivityCreate(SeckillActivityBase):
    pass


class SeckillActivityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="活动名称")
    description: Optional[str] = Field(None, max_length=255, description="活动描述")
    start_time: Optional[datetime] = Field(None, description="秒杀开始时间")
    end_time: Optional[datetime] = Field(None, description="秒杀结束时间")
    status: Optional[SeckillActivityStatus] = Field(None, description="活动状态")


class SeckillActivity(SeckillActivityBase):
    id: int
    status: SeckillActivityStatus
    products: List[SeckillProduct] = []

    class Config:
        from_attributes = True


class SeckillActivityPublic(SeckillActivityBase):
    id: int
    status: SeckillActivityStatus

    class Config:
        from_attributes = True


# --- SeckillOrder Schemas ---

class SeckillOrderCreate(BaseModel):
    """
    用于创建秒杀订单的输入模型
    """
    sku_id: int = Field(..., description="商品SKU ID")
    quantity: int = Field(..., gt=0, description="购买数量")
    receiver_name: str = Field(..., max_length=100, description="收货人姓名")
    receiver_phone: str = Field(..., description="收货人手机号")
    receiver_address: str = Field(..., max_length=255, description="收货地址")
    notes: Optional[str] = Field(None, max_length=500, description="订单备注")

    @field_validator('receiver_phone')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """验证手机号码是否合法"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('无效的手机号码格式')
        return v


class SeckillOrderResponse(BaseModel):
    """
    秒杀下单请求的响应模型
    """
    request_id: str = Field(..., description="用于查询订单处理状态的唯一请求ID")


class SeckillOrderStatus(BaseModel):
    """
    秒杀订单状态查询的响应模型
    """
    status: str = Field(..., description="处理状态 (PROCESSING, SUCCESS, FAILED)")
    message: Optional[str] = Field(None, description="相关信息")
    order_id: Optional[int] = Field(None, description="如果成功，则为创建的订单ID")
    order_sn: Optional[str] = Field(None, description="如果成功，则为创建的订单号")
