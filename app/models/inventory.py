from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.product_attribute import SKU
    from app.models.user import User


class Warehouse(Base):
    """仓库模型"""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    inventory_items: Mapped[List["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="warehouse", cascade="all, delete-orphan"
    )


class InventoryItem(Base):
    """库存项模型 - 记录每个SKU在每个仓库的库存情况"""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 已预留但未确认的数量
    alert_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # 库存预警阈值
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    sku: Mapped["SKU"] = relationship("SKU", backref="inventory_items")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="inventory_items")
    inventory_transactions: Mapped[List["InventoryTransaction"]] = relationship(
        "InventoryTransaction", back_populates="inventory_item", cascade="all, delete-orphan"
    )

    # 唯一约束：每个SKU在每个仓库只能有一条记录
    __table_args__ = (
        UniqueConstraint('sku_id', 'warehouse_id', name='uix_inventory_sku_warehouse'),
    )


class InventoryTransactionType(str, Enum):
    """库存事务类型枚举"""
    STOCK_IN = "stock_in"  # 入库
    STOCK_OUT = "stock_out"  # 出库
    RESERVE = "reserve"  # 预留库存
    RELEASE = "release"  # 释放预留库存
    ADJUST = "adjust"  # 库存调整
    TRANSFER_IN = "transfer_in"  # 调拨入库
    TRANSFER_OUT = "transfer_out"  # 调拨出库


class InventoryTransaction(Base):
    """库存事务模型 - 记录所有库存变动"""

    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    inventory_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # 可以是正数或负数，表示增加或减少
    reference_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 关联ID（如订单ID）
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 关联类型（如"order"）
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    inventory_item: Mapped["InventoryItem"] = relationship("InventoryItem", back_populates="inventory_transactions")
    operator: Mapped[Optional["User"]] = relationship("User")
