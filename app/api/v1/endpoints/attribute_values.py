from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product_attribute import AttributeValue, Attribute, SKU, sku_attribute_value
from app.models.user import User
from app.schemas.product_attribute import (
    AttributeValue as AttributeValueSchema,
    AttributeValueCreate,
    AttributeValueUpdate,
    AttributeValueWithAttribute,
)

router = APIRouter()


@router.get("/", response_model=List[AttributeValueWithAttribute])
async def list_attribute_values(
        skip: int = 0,
        limit: int = 100,
        attribute_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db),
):
    """
    获取属性值列表，可选择按属性ID筛选
    """
    # 首先获取属性值列表
    query = select(AttributeValue).options(selectinload(AttributeValue.attribute))

    if attribute_id is not None:
        query = query.where(AttributeValue.attribute_id == attribute_id)

    query = query.offset(skip).limit(limit).order_by(AttributeValue.sort_order.desc())
    result = await db.execute(query)
    attribute_values = result.scalars().all()

    # 获取所有相关的属性ID
    attribute_ids = [av.attribute_id for av in attribute_values]

    # 预加载属性及其values关系
    if attribute_ids:
        attributes_result = await db.execute(
            select(Attribute)
            .options(selectinload(Attribute.values))
            .where(Attribute.id.in_(attribute_ids))
        )
        attributes = {attr.id: attr for attr in attributes_result.scalars().all()}

        # 手动设置预加载的属性对象
        for av in attribute_values:
            if av.attribute_id in attributes:
                av.attribute = attributes[av.attribute_id]

    return attribute_values


@router.get("/{value_id}", response_model=AttributeValueWithAttribute)
async def get_attribute_value(
        value_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定属性值详情
    """
    # 获取属性值
    result = await db.execute(
        select(AttributeValue)
        .options(selectinload(AttributeValue.attribute))
        .where(AttributeValue.id == value_id)
    )
    attribute_value = result.scalars().first()

    if attribute_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性值不存在")

    # 预加载属性的values关系
    if attribute_value.attribute_id:
        attribute_result = await db.execute(
            select(Attribute)
            .options(selectinload(Attribute.values))
            .where(Attribute.id == attribute_value.attribute_id)
        )
        attribute = attribute_result.scalars().first()
        if attribute:
            attribute_value.attribute = attribute

    return attribute_value


@router.post("/", response_model=AttributeValueSchema, status_code=status.HTTP_201_CREATED)
async def create_attribute_value(
        attribute_value: AttributeValueCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新属性值
    """
    # 检查属性是否存在
    result = await db.execute(select(Attribute).where(Attribute.id == attribute_value.attribute_id))
    attribute = result.scalars().first()
    if attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所属属性不存在")

    db_attribute_value = AttributeValue(**attribute_value.model_dump())
    db.add(db_attribute_value)
    await db.commit()
    await db.refresh(db_attribute_value)

    # 这里不需要预加载attribute.values关系，因为返回的是AttributeValueSchema，不包含attribute字段

    return db_attribute_value


@router.put("/{value_id}", response_model=AttributeValueSchema)
async def update_attribute_value(
        value_id: int,
        attribute_value_update: AttributeValueUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新属性值
    """
    # 查询属性值是否存在
    result = await db.execute(select(AttributeValue).where(AttributeValue.id == value_id))
    db_attribute_value = result.scalars().first()
    if db_attribute_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性值不存在")

    # 如果更新了属性ID，检查新属性是否存在
    update_data = attribute_value_update.model_dump(exclude_unset=True)
    if "attribute_id" in update_data and update_data["attribute_id"] != db_attribute_value.attribute_id:
        attribute_result = await db.execute(
            select(Attribute).where(Attribute.id == update_data["attribute_id"])
        )
        attribute = attribute_result.scalars().first()
        if attribute is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所属属性不存在")

    # 检查属性值是否关联了SKU
    if "attribute_id" in update_data or "value" in update_data:
        sku_count_result = await db.execute(
            select(func.count())
            .select_from(SKU)
            .join(sku_attribute_value)
            .where(sku_attribute_value.c.attribute_value_id == value_id)
        )
        sku_count = sku_count_result.scalar()
        if sku_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该属性值已关联SKU，无法修改属性ID或值",
            )

    # 更新属性值字段
    for key, value in update_data.items():
        setattr(db_attribute_value, key, value)

    await db.commit()
    await db.refresh(db_attribute_value)
    return db_attribute_value


@router.delete("/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute_value(
        value_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除属性值
    """
    # 查询属性值是否存在
    result = await db.execute(select(AttributeValue).where(AttributeValue.id == value_id))
    attribute_value = result.scalars().first()
    if attribute_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性值不存在")

    # 检查属性值是否关联了SKU
    sku_count_result = await db.execute(
        select(func.count())
        .select_from(SKU)
        .join(sku_attribute_value)
        .where(sku_attribute_value.c.attribute_value_id == value_id)
    )
    sku_count = sku_count_result.scalar()
    if sku_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该属性值已关联SKU，无法删除",
        )

    # 删除属性值
    await db.delete(attribute_value)
    await db.commit()

    return None
