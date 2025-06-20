from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

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
