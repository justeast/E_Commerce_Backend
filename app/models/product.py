from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Table, Column, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# 使用TYPE_CHECKING避免循环导入
if TYPE_CHECKING:
    from app.models.product_attribute import SKU
    from app.models.product_review import ProductReview

# 商品-标签关联表（多对多）
product_tag = Table(
    "product_tag",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Category(Base):
    """商品分类模型"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 父分类ID，允许为空（顶级分类）
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    # 是否显示在导航中
    is_navigation: Mapped[bool] = mapped_column(Boolean, default=True)
    # 排序权重（数字越大越靠前）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 分类图标URL
    icon_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    # 子分类（一对多）
    children: Mapped[List["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id]
    )
    # 父分类（多对一）
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="children",
        remote_side=[id]
    )
    # 该分类下的商品（一对多）
    products: Mapped[List["Product"]] = relationship(
        "Product",
        back_populates="category",
        cascade="all, delete-orphan"
    )


class Tag(Base):
    """商品标签模型"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 标签颜色（可用于前端展示）
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    # 拥有此标签的商品（多对多）
    products: Mapped[List["Product"]] = relationship(
        "Product",
        secondary=product_tag,
        back_populates="tags"
    )


class Product(Base):
    """商品基本信息模型"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # 商品价格
    price: Mapped[float] = mapped_column(Float, nullable=False)
    # 商品库存
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 商品分类ID
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    # 是否上架
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    # 所属分类（多对一）
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    # 商品标签（多对多）
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=product_tag,
        back_populates="products"
    )
    # 商品SKU（一对多）
    skus: Mapped[List["SKU"]] = relationship(
        "SKU",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    reviews: Mapped[List["ProductReview"]] = relationship(
        "ProductReview",
        back_populates="product",
        cascade="all, delete-orphan"
    )
