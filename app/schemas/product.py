from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# 标签模型
class TagBase(BaseModel):
    name: str = Field(..., description="标签名称", max_length=50)
    description: Optional[str] = Field(None, description="标签描述", max_length=200)
    color: Optional[str] = Field(None, description="标签颜色", max_length=20)


class TagCreate(TagBase):
    pass


class TagUpdate(TagBase):
    name: Optional[str] = Field(None, description="标签名称", max_length=50)


class Tag(TagBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 分类模型
class CategoryBase(BaseModel):
    name: str = Field(..., description="分类名称", max_length=100)
    description: Optional[str] = Field(None, description="分类描述", max_length=200)
    parent_id: Optional[int] = Field(None, description="父分类ID")
    is_navigation: bool = Field(True, description="是否显示在导航中")
    sort_order: int = Field(0, description="排序权重（数字越大越靠前）")
    icon_url: Optional[str] = Field(None, description="分类图标URL", max_length=255)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    name: Optional[str] = Field(None, description="分类名称", max_length=100)


class CategorySimple(BaseModel):
    """简化的分类信息，用于嵌套展示"""
    id: int
    name: str
    icon_url: Optional[str] = None

    class Config:
        from_attributes = True


class Category(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    parent: Optional[CategorySimple] = None
    children: List[CategorySimple] = []

    class Config:
        from_attributes = True


class CategoryTree(CategoryBase):
    """用于树形结构展示的分类模型"""
    id: int
    children: List["CategoryTree"] = []

    class Config:
        from_attributes = True


# 递归引用需要在定义后更新
CategoryTree.model_rebuild()


# 商品基本模型
class ProductBase(BaseModel):
    name: str = Field(..., description="商品名称", max_length=100)
    description: Optional[str] = Field(None, description="商品描述", max_length=1000)
    price: float = Field(..., description="商品价格", gt=0)
    stock: int = Field(0, description="商品库存", ge=0)
    category_id: int = Field(..., description="商品分类ID")
    is_active: bool = Field(True, description="是否上架")


class ProductCreate(ProductBase):
    tag_ids: Optional[List[int]] = Field(None, description="商品标签ID列表")


class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, description="商品名称", max_length=100)
    description: Optional[str] = Field(None, description="商品描述", max_length=1000)
    price: Optional[float] = Field(None, description="商品价格", gt=0)
    stock: Optional[int] = Field(None, description="商品库存", ge=0)
    category_id: Optional[int] = Field(None, description="商品分类ID")
    is_active: Optional[bool] = Field(None, description="是否上架")
    tag_ids: Optional[List[int]] = Field(None, description="商品标签ID列表")


class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category: CategorySimple
    tags: List[Tag] = []

    class Config:
        from_attributes = True
