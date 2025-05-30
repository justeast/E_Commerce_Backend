from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# 评价基础模型
class ProductReviewBase(BaseModel):
    product_id: int = Field(..., description="商品ID")
    rating: int = Field(..., description="评分(1-5)", ge=1, le=5)
    content: Optional[str] = Field(None, description="评价内容")
    images: Optional[str] = Field(None, description="评价图片，多个图片URL以逗号分隔")
    is_anonymous: bool = Field(False, description="是否匿名评价")

    @field_validator('content')
    def validate_content_length(cls, v):
        if v and len(v) > 2000:
            raise ValueError('评价内容不能超过2000个字符')
        return v

    @field_validator('images')
    def validate_images_count(cls, v):
        if v:
            # 计算图片数量
            image_count = len(v.split(','))
            if image_count > 9:
                raise ValueError('最多只能上传9张图片')
        return v


# 创建评价请求模型
class ProductReviewCreate(ProductReviewBase):
    order_id: Optional[int] = Field(None, description="订单ID")


# 更新评价请求模型
class ProductReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, description="评分(1-5)", ge=1, le=5)
    content: Optional[str] = Field(None, description="评价内容")
    images: Optional[str] = Field(None, description="评价图片，多个图片URL以逗号分隔")
    is_anonymous: Optional[bool] = Field(None, description="是否匿名评价")

    @field_validator('content')
    def validate_content_length(cls, v):
        if v and len(v) > 2000:
            raise ValueError('评价内容不能超过2000个字符')
        return v

    @field_validator('images')
    def validate_images_count(cls, v):
        if v:
            # 计算图片数量
            image_count = len(v.split(','))
            if image_count > 9:
                raise ValueError('最多只能上传9张图片')
        return v


# 评价回复基础模型
class ReviewReplyBase(BaseModel):
    content: str = Field(..., description="回复内容")

    @field_validator('content')
    def validate_content(cls, v):
        if not v:
            raise ValueError('回复内容不能为空')
        if len(v) > 1000:
            raise ValueError('回复内容不能超过1000个字符')
        return v


# 创建评价回复请求模型
class ReviewReplyCreate(ReviewReplyBase):
    pass


# 更新评价回复请求模型
class ReviewReplyUpdate(BaseModel):
    content: Optional[str] = Field(None, description="回复内容")

    @field_validator('content')
    def validate_content(cls, v):
        if v is not None:
            if not v:
                raise ValueError('回复内容不能为空')
            if len(v) > 1000:
                raise ValueError('回复内容不能超过1000个字符')
        return v


# 评价回复响应模型
class ReviewReply(ReviewReplyBase):
    id: int
    review_id: int
    user_id: int
    is_merchant: bool
    created_at: datetime
    updated_at: datetime

    # 用户信息（可选，取决于是否匿名）
    username: Optional[str] = None

    class Config:
        from_attributes = True


# 评价响应模型
class ProductReview(ProductReviewBase):
    id: int
    user_id: int
    order_id: Optional[int] = None
    is_verified_purchase: bool
    created_at: datetime
    updated_at: datetime

    # 用户信息（可选，取决于是否匿名）
    username: Optional[str] = None

    # 回复列表
    replies: List[ReviewReply] = []

    class Config:
        from_attributes = True


# 商品评价统计模型
class ProductReviewStats(BaseModel):
    product_id: int
    average_rating: float = Field(..., description="平均评分")
    total_reviews: int = Field(..., description="总评价数")
    rating_distribution: dict = Field(..., description="评分分布，如 {5: 10, 4: 5, 3: 2, 2: 1, 1: 0}")
