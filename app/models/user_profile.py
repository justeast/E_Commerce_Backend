from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserProfileTag(Base):
    """
    用户画像标签
    允许灵活扩展：key = 维度名；value = 具体标签；weight = 置信度/权重
    例如：
        key="interest_category", value="electronics"
        key="price_sensitivity", value="high"
    """
    __tablename__ = "user_profile_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    tag_key: Mapped[str] = mapped_column(String(64))
    tag_value: Mapped[str] = mapped_column(String(128))
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="profile_tags")
