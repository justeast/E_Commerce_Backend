from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator

from app.models.coupon import CouponStatus, CouponType


# CouponTemplate Schemas

class CouponTemplateBase(BaseModel):
    name: str = Field(..., max_length=100, description="优惠券名称")
    type: CouponType = Field(..., description="优惠券类型")
    value: Decimal = Field(..., gt=0, description="面值或折扣率")
    min_spend: Decimal = Field(Decimal("0.0"), ge=0, description="最低消费金额")
    valid_from: Optional[datetime] = Field(None, description="有效期开始时间")
    valid_to: Optional[datetime] = Field(None, description="有效期结束时间")
    total_quantity: int = Field(0, ge=0, description="发行总量, 0为不限制")
    usage_limit_per_user: int = Field(1, ge=1, description="每位用户可领取/使用上限")
    is_active: bool = Field(True, description="是否激活")


class CouponTemplateCreate(CouponTemplateBase):
    code_prefix: Optional[str] = Field(None, max_length=20, description="优惠券码前缀, 留空则为通用券")

    @model_validator(mode='after')
    def check_dates(self) -> 'CouponTemplateCreate':
        if self.valid_from and self.valid_to:
            if self.valid_to <= self.valid_from:
                raise ValueError('结束时间必须晚于开始时间')
        return self


class CouponTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    total_quantity: Optional[int] = Field(None, ge=0)
    usage_limit_per_user: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    @model_validator(mode='after')
    def check_dates(self) -> 'CouponTemplateUpdate':
        if self.valid_from and self.valid_to:
            if self.valid_to <= self.valid_from:
                raise ValueError('结束时间必须晚于开始时间')
        return self


class CouponTemplateInDB(CouponTemplateBase):
    id: int
    code_prefix: Optional[str]
    issued_quantity: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CouponTemplateListResponse(BaseModel):
    items: List[CouponTemplateInDB]
    total: int


class CouponTemplate(CouponTemplateInDB):
    pass


# UserCoupon Schemas

class UserCouponBase(BaseModel):
    user_id: int
    coupon_template_id: int
    code: str
    status: CouponStatus


class UserCouponCreate(BaseModel):
    user_id: int
    coupon_template_id: int


class UserCouponInDB(UserCouponBase):
    id: int
    claimed_at: datetime
    used_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCoupon(UserCouponInDB):
    template: CouponTemplate


class UserCouponWithTemplate(BaseModel):
    id: int
    code: str
    status: CouponStatus
    claimed_at: datetime
    used_at: Optional[datetime]
    template: CouponTemplate

    class Config:
        from_attributes = True


class UserCouponListResponse(BaseModel):
    items: List[UserCouponWithTemplate]
    total: int
