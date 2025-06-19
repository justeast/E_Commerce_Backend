import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (DateTime, Enum, Numeric, ForeignKey, Integer,
                        String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa
    from .product_attribute import SKU  # noqa
    from .promotion import Promotion  # noqa
    from .coupon import UserCoupon  # noqa


class OrderStatusEnum(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"  # 待支付
    PROCESSING = "processing"  # 处理中（已支付）
    SHIPPED = "shipped"  # 已发货
    DELIVERED = "delivered"  # 已送达
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消
    REFUNDED = "refunded"  # 已退款


class PaymentMethodEnum(str, enum.Enum):
    ALIPAY = "alipay"  # 支付宝
    WECHAT_PAY = "wechat_pay"  # 微信支付
    OTHER = "other"  # 其他


class Cart(Base):
    """购物车模型"""
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="cart")
    items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    """购物车项目模型"""
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id"), nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # 添加时SKU的价格，防止SKU价格变动影响购物车显示
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    sku: Mapped["SKU"] = relationship("SKU", back_populates="cart_items", lazy="joined")


class Order(Base):
    """订单模型"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_sn: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pay_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.0'))
    promotion_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.0'))
    coupon_discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.0'),
                                                            comment="优惠券抵扣金额")

    status: Mapped[OrderStatusEnum] = mapped_column(Enum(OrderStatusEnum), default=OrderStatusEnum.PENDING_PAYMENT)
    payment_method: Mapped[Optional[PaymentMethodEnum]] = mapped_column(Enum(PaymentMethodEnum), nullable=True)

    # 支付相关
    trade_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 支付平台交易号
    pay_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 收货人信息
    receiver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_address: Mapped[str] = mapped_column(String(255), nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    promotion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("promotion.id"), nullable=True,
                                                        comment="应用的促销活动ID")

    user_coupon_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_coupons.id"), nullable=True,
                                                          comment="使用的用户优惠券ID")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    promotion: Mapped[Optional["Promotion"]] = relationship("Promotion", back_populates="orders", lazy="joined")
    user_coupon: Mapped[Optional["UserCoupon"]] = relationship("UserCoupon", back_populates="order")
    logs: Mapped[List["OrderLog"]] = relationship("OrderLog", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """订单项目模型"""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)

    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 关联
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    sku: Mapped["SKU"] = relationship("SKU", back_populates="order_items", lazy="joined")


class OrderLog(Base):
    """订单操作日志模型"""
    __tablename__ = "order_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # None表示系统操作
    from_status: Mapped[Optional[OrderStatusEnum]] = mapped_column(Enum(OrderStatusEnum), nullable=True)
    to_status: Mapped[OrderStatusEnum] = mapped_column(Enum(OrderStatusEnum), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    order: Mapped["Order"] = relationship("Order", back_populates="logs")
    operator: Mapped[Optional["User"]] = relationship("User")
