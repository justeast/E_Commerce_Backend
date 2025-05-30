from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product_attribute import Attribute, AttributeValue
from app.models.user import User
from app.schemas.product_attribute import (
    Attribute as AttributeSchema,
    AttributeCreate,
    AttributeUpdate,
)
from app.models.product_attribute import SKU, sku_attribute_value

router = APIRouter()


@router.get("/", response_model=List[AttributeSchema])
async def list_attributes(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
):
    """
    获取属性列表
    """
    query = select(Attribute).offset(skip).limit(limit).order_by(Attribute.sort_order.desc())
    query = query.options(selectinload(Attribute.values))
    result = await db.execute(query)
    attributes = result.scalars().all()
    return attributes


@router.get("/{attribute_id}", response_model=AttributeSchema)
async def get_attribute(
        attribute_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定属性详情
    """
    result = await db.execute(
        select(Attribute)
        .options(selectinload(Attribute.values))
        .where(Attribute.id == attribute_id)
    )
    attribute = result.scalars().first()
    if attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性不存在")
    return attribute


@router.post("/", response_model=AttributeSchema, status_code=status.HTTP_201_CREATED)
async def create_attribute(
        attribute: AttributeCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新属性
    """
    db_attribute = Attribute(**attribute.model_dump())
    db.add(db_attribute)
    await db.commit()
    await db.refresh(db_attribute)

    # 预加载values关系
    result = await db.execute(
        select(Attribute)
        .options(selectinload(Attribute.values))
        .where(Attribute.id == db_attribute.id)
    )
    db_attribute_with_values = result.scalars().first()

    return db_attribute_with_values


@router.put("/{attribute_id}", response_model=AttributeSchema)
async def update_attribute(
        attribute_id: int,
        attribute_update: AttributeUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新属性
    """
    result = await db.execute(select(Attribute).where(Attribute.id == attribute_id))
    db_attribute = result.scalars().first()
    if db_attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性不存在")

    update_data = attribute_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_attribute, key, value)

    await db.commit()
    await db.refresh(db_attribute)

    # 预加载values关系
    result = await db.execute(
        select(Attribute)
        .options(selectinload(Attribute.values))
        .where(Attribute.id == attribute_id)
    )
    db_attribute_with_values = result.scalars().first()

    return db_attribute_with_values


@router.delete("/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute(
        attribute_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除属性
    """
    # 查询属性是否存在
    result = await db.execute(select(Attribute).where(Attribute.id == attribute_id))
    attribute = result.scalars().first()
    if attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="属性不存在")

    # 检查属性是否有关联的SKU
    # 这里我们通过检查属性值是否关联了SKU来间接检查
    attribute_values_result = await db.execute(
        select(AttributeValue).where(AttributeValue.attribute_id == attribute_id)
    )
    attribute_values = attribute_values_result.scalars().all()

    for value in attribute_values:
        # 使用直接的SQL查询检查属性值是否关联了SKU
        sku_count_result = await db.execute(
            select(func.count())
            .select_from(SKU)
            .join(sku_attribute_value)
            .where(sku_attribute_value.c.attribute_value_id == value.id)
        )
        sku_count = sku_count_result.scalar()
        if sku_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"属性值 '{value.value}' 已关联SKU，无法删除属性",
            )

    # 删除属性（会级联删除属性值）
    await db.delete(attribute)
    await db.commit()

    return None
