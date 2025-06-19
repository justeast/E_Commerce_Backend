import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa
    from .order import Order  # noqa


class CouponType(str, enum.Enum):
    FIXED = "FIXED"  # 固定金额
    PERCENTAGE = "PERCENTAGE"  # 百分比折扣


class CouponStatus(str, enum.Enum):
    UNUSED = "UNUSED"
    USED = "USED"
    EXPIRED = "EXPIRED"


class CouponTemplate(Base):
    """优惠券模板"""
    __tablename__ = "coupon_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="优惠券名称")
    code_prefix: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True, nullable=True,
                                                       comment="优惠券码前缀")
    type: Mapped[CouponType] = mapped_column(SAEnum(CouponType), nullable=False, comment="优惠券类型")
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="面值或折扣率")
    min_spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.0"),
                                               comment="最低消费金额")
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                           comment="有效期开始时间")
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                         comment="有效期结束时间")
    total_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="发行总量, 0为不限制")
    issued_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="已发行数量")
    usage_limit_per_user: Mapped[int] = mapped_column(Integer, default=1, comment="每位用户可领取/使用上限")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user_coupons: Mapped[List["UserCoupon"]] = relationship("UserCoupon", back_populates="template")


class UserCoupon(Base):
    """用户领取的优惠券"""
    __tablename__ = "user_coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    coupon_template_id: Mapped[int] = mapped_column(Integer, ForeignKey("coupon_templates.id"), nullable=False,
                                                    index=True)

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="唯一的优惠券码")
    status: Mapped[CouponStatus] = mapped_column(SAEnum(CouponStatus), default=CouponStatus.UNUSED, nullable=False,
                                                 index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                                 comment="领取时间")
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="使用时间")

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="coupons")
    template: Mapped["CouponTemplate"] = relationship("CouponTemplate", back_populates="user_coupons")
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="user_coupon", uselist=False)
