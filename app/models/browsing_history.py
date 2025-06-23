from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.product_attribute import SKU


class BrowsingHistory(Base):
    """
    用户浏览历史记录
    """
    __tablename__ = "browsing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                                         index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False, index=True)
    browsed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="browsing_history")
    sku: Mapped["SKU"] = relationship("SKU", back_populates="browsing_histories")
