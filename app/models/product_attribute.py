from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Table, Column, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# 使用TYPE_CHECKING避免循环导入
if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.order import CartItem, OrderItem

# SKU-属性值关联表（多对多）
sku_attribute_value = Table(
    "sku_attribute_value",
    Base.metadata,
    Column("sku_id", Integer, ForeignKey("skus.id"), primary_key=True),
    Column("attribute_value_id", Integer, ForeignKey("attribute_values.id"), primary_key=True),
)


class Attribute(Base):
    """商品属性模型（如颜色、尺寸、材质等）"""

    __tablename__ = "attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 属性类型：可选值如 'select'（单选）, 'multiple'（多选）, 'input'（输入框）等
    input_type: Mapped[str] = mapped_column(String(20), default="select")
    # 是否用于SKU生成
    is_sku: Mapped[bool] = mapped_column(Boolean, default=True)
    # 排序权重
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联的属性值
    values: Mapped[List["AttributeValue"]] = relationship("AttributeValue", back_populates="attribute",
                                                          cascade="all, delete-orphan")


class AttributeValue(Base):
    """属性值模型（如红色、蓝色、S、M、L等）"""

    __tablename__ = "attribute_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    value: Mapped[str] = mapped_column(String(50), nullable=False)
    # 附加信息（如颜色代码、图片URL等）
    extra: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 排序权重
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    attribute_id: Mapped[int] = mapped_column(Integer, ForeignKey("attributes.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联的属性
    attribute: Mapped["Attribute"] = relationship("Attribute", back_populates="values")
    # 关联的SKU
    skus: Mapped[List["SKU"]] = relationship("SKU", secondary=sku_attribute_value, back_populates="attribute_values")


class SKU(Base):
    """SKU模型（库存单位）"""

    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    # SKU编码（如条形码、自定义编码等）
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    # SKU名称（通常是商品名称 + 属性组合）
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # SKU价格（可能与商品基础价格不同）
    price: Mapped[float] = mapped_column(Float, nullable=False)
    # SKU库存
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 图片URL（可能与商品主图不同）
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联的商品
    product: Mapped["Product"] = relationship("Product", back_populates="skus")
    # 关联的属性值
    attribute_values: Mapped[List["AttributeValue"]] = relationship(
        "AttributeValue", secondary=sku_attribute_value, back_populates="skus"
    )

    cart_items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="sku"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="sku"
    )

    # 确保每个商品的SKU属性值组合是唯一的
    __table_args__ = (
        UniqueConstraint('product_id', 'name', name='uix_sku_product_name'),
    )
