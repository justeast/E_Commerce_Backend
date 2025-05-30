from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# 属性模型
class AttributeBase(BaseModel):
    name: str = Field(..., description="属性名称", max_length=50)
    description: Optional[str] = Field(None, description="属性描述", max_length=200)
    input_type: str = Field("select", description="输入类型：select(单选)、multiple(多选)、input(输入框)等", max_length=20)
    is_sku: bool = Field(True, description="是否用于SKU生成")
    sort_order: int = Field(0, description="排序权重（数字越大越靠前）")


class AttributeCreate(AttributeBase):
    pass


class AttributeUpdate(AttributeBase):
    name: Optional[str] = Field(None, description="属性名称", max_length=50)
    description: Optional[str] = Field(None, description="属性描述", max_length=200)
    input_type: Optional[str] = Field(None, description="输入类型", max_length=20)
    is_sku: Optional[bool] = Field(None, description="是否用于SKU生成")
    sort_order: Optional[int] = Field(None, description="排序权重")


# 属性值模型
class AttributeValueBase(BaseModel):
    value: str = Field(..., description="属性值", max_length=50)
    extra: Optional[str] = Field(None, description="附加信息（如颜色代码、图片URL等）", max_length=255)
    sort_order: int = Field(0, description="排序权重（数字越大越靠前）")
    attribute_id: int = Field(..., description="所属属性ID")


class AttributeValueCreate(AttributeValueBase):
    pass


class AttributeValueUpdate(AttributeValueBase):
    value: Optional[str] = Field(None, description="属性值", max_length=50)
    extra: Optional[str] = Field(None, description="附加信息", max_length=255)
    sort_order: Optional[int] = Field(None, description="排序权重")
    attribute_id: Optional[int] = Field(None, description="所属属性ID")


# SKU模型
class SKUBase(BaseModel):
    product_id: int = Field(..., description="商品ID")
    code: Optional[str] = Field(None, description="SKU编码", max_length=50)
    name: str = Field(..., description="SKU名称", max_length=200)
    price: float = Field(..., description="SKU价格", gt=0)
    stock: int = Field(0, description="SKU库存", ge=0)
    is_active: bool = Field(True, description="是否启用")
    image_url: Optional[str] = Field(None, description="图片URL", max_length=255)


class SKUCreate(SKUBase):
    attribute_value_ids: List[int] = Field(..., description="属性值ID列表")


class SKUUpdate(SKUBase):
    product_id: Optional[int] = Field(None, description="商品ID")
    code: Optional[str] = Field(None, description="SKU编码", max_length=50)
    name: Optional[str] = Field(None, description="SKU名称", max_length=200)
    price: Optional[float] = Field(None, description="SKU价格", gt=0)
    stock: Optional[int] = Field(None, description="SKU库存", ge=0)
    is_active: Optional[bool] = Field(None, description="是否启用")
    image_url: Optional[str] = Field(None, description="图片URL", max_length=255)
    attribute_value_ids: Optional[List[int]] = Field(None, description="属性值ID列表")


# 响应模型
class AttributeValue(AttributeValueBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Attribute(AttributeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    values: List[AttributeValue] = []

    class Config:
        from_attributes = True


class AttributeValueWithAttribute(AttributeValue):
    attribute: Attribute

    class Config:
        from_attributes = True


class SKU(SKUBase):
    id: int
    created_at: datetime
    updated_at: datetime
    attribute_values: List[AttributeValue] = []

    class Config:
        from_attributes = True


# 商品详情中包含SKU信息的模型
class ProductWithSKUs(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    skus: List[SKU] = []

    class Config:
        from_attributes = True


# 批量生成SKU的请求模型
class GenerateSKUsRequest(BaseModel):
    product_id: int = Field(..., description="商品ID")
    attribute_ids: List[int] = Field(..., description="用于生成SKU的属性ID列表")
    price_increment: Optional[float] = Field(0, description="SKU价格增量（相对于商品基础价格）")
    stock_initial: Optional[int] = Field(0, description="SKU初始库存")
