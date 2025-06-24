from datetime import datetime, timezone
from typing import List, TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.rbac import user_role
from app.models.user_profile import UserProfileTag

if TYPE_CHECKING:
    from app.models.rbac import Role
    from app.models.product_review import ProductReview, ReviewReply
    from app.models.order import Cart, Order
    from app.models.coupon import UserCoupon
    from app.models.browsing_history import BrowsingHistory


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关联
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_role, back_populates="users"
    )
    product_reviews: Mapped[List["ProductReview"]] = relationship(
        "ProductReview", back_populates="user", cascade="all, delete-orphan"
    )
    review_replies: Mapped[List["ReviewReply"]] = relationship(
        "ReviewReply", back_populates="user", cascade="all, delete-orphan"
    )

    cart: Mapped[Optional["Cart"]] = relationship(
        "Cart", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )

    coupons: Mapped[List["UserCoupon"]] = relationship(
        "UserCoupon", back_populates="user", cascade="all, delete-orphan"
    )

    browsing_history: Mapped[List["BrowsingHistory"]] = relationship(
        "BrowsingHistory", back_populates="user", cascade="all, delete-orphan"
    )

    profile_tags: Mapped[List["UserProfileTag"]] = relationship(
        "UserProfileTag",
        back_populates="user",
        cascade="all, delete-orphan",
    )
