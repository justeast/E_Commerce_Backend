from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProductReview(Base):
    """商品评价模型"""
    __tablename__ = "product_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    # 暂时移除对orders表的外键引用，改为普通整数字段
    order_id = Column(Integer, nullable=True, comment="订单ID")
    rating = Column(Integer, nullable=False, comment="评分(1-5)")
    content = Column(Text, nullable=True, comment="评价内容")
    images = Column(String(1000), nullable=True, comment="评价图片，多个图片URL以逗号分隔")
    is_anonymous = Column(Boolean, default=False, comment="是否匿名评价")
    is_verified_purchase = Column(Boolean, default=False, comment="是否已验证购买")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    user = relationship("User", back_populates="product_reviews")
    product = relationship("Product", back_populates="reviews")
    replies = relationship("ReviewReply", back_populates="review", cascade="all, delete-orphan")


class ReviewReply(Base):
    """评价回复模型"""
    __tablename__ = "review_replies"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("product_reviews.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, comment="回复内容")
    is_merchant = Column(Boolean, default=False, comment="是否商家回复")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    review = relationship("ProductReview", back_populates="replies")
    user = relationship("User", back_populates="review_replies")
