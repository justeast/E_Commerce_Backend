import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.product_attribute import SKU


# 秒杀活动状态
class SeckillActivityStatus(str, enum.Enum):
    PENDING = "PENDING"  # 未开始
    ACTIVE = "ACTIVE"  # 进行中
    ENDED = "ENDED"  # 已结束
    CANCELLED = "CANCELLED"  # 已取消


class SeckillActivity(Base):
    __tablename__ = "seckill_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="活动名称")
    description: Mapped[str] = mapped_column(String(255), nullable=True, comment="活动描述")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="秒杀开始时间")
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="秒杀结束时间")
    status: Mapped[SeckillActivityStatus] = mapped_column(
        Enum(SeckillActivityStatus), nullable=False, default=SeckillActivityStatus.PENDING, comment="活动状态"
    )

    # 与 SeckillProduct 的关系
    products: Mapped[List["SeckillProduct"]] = relationship(
        "SeckillProduct", back_populates="activity", cascade="all, delete-orphan"
    )


class SeckillProduct(Base):
    __tablename__ = "seckill_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    activity_id: Mapped[int] = mapped_column(Integer, ForeignKey("seckill_activities.id"), nullable=False,
                                             comment="秒杀活动ID")
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False, comment="商品SKUID")
    seckill_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="秒杀价")
    seckill_stock: Mapped[int] = mapped_column(Integer, nullable=False, comment="秒杀库存")
    purchase_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="每人限购数量")

    # 关联
    activity: Mapped["SeckillActivity"] = relationship("SeckillActivity", back_populates="products")
    sku: Mapped["SKU"] = relationship("SKU", back_populates="seckill_products")
