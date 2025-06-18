from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.promotion import (
    PromotionTargetType,
    PromotionConditionType,
    PromotionActionType,
)


class PromotionBase(BaseModel):
    name: str = Field(..., max_length=100, description="促销活动名称")
    description: Optional[str] = Field(None, max_length=255, description="促销活动描述")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    is_active: bool = Field(True, description="是否激活")
    target_type: PromotionTargetType = Field(PromotionTargetType.ALL, description="促销适用目标类型")
    target_ids: Optional[List[int]] = Field(None, description="目标ID列表")
    condition_type: PromotionConditionType = Field(PromotionConditionType.NO_THRESHOLD, description="触发条件类型")
    condition_value: Optional[Decimal] = Field(None, description="触发条件的值")
    action_type: PromotionActionType = Field(..., description="优惠动作类型")
    action_value: Decimal = Field(..., description="优惠动作的值")


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="促销活动名称")
    description: Optional[str] = Field(None, max_length=255, description="促销活动描述")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    is_active: Optional[bool] = Field(None, description="是否激活")
    target_type: Optional[PromotionTargetType] = Field(None, description="促销适用目标类型")
    target_ids: Optional[List[int]] = Field(None, description="目标ID列表")
    condition_type: Optional[PromotionConditionType] = Field(None, description="触发条件类型")
    condition_value: Optional[Decimal] = Field(None, description="触发条件的值")
    action_type: Optional[PromotionActionType] = Field(None, description="优惠动作类型")
    action_value: Optional[Decimal] = Field(None, description="优惠动作的值")


class Promotion(PromotionBase):
    id: int

    class Config:
        from_attributes = True
