from typing import List, Optional
from itertools import product as itertools_product

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product import Product
from app.models.product_attribute import SKU, Attribute, AttributeValue
from app.models.user import User
from app.schemas.product_attribute import (
    SKU as SKUSchema,
    SKUCreate,
    SKUUpdate,
    GenerateSKUsRequest,
)

router = APIRouter()


@router.get("/", response_model=List[SKUSchema], summary="获取SKU列表")
async def list_skus(
        skip: int = 0,
        limit: int = 100,
        product_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db),
):
    """
    获取SKU列表，可选择按商品ID筛选
    """
    query = select(SKU).options(selectinload(SKU.attribute_values))

    if product_id is not None:
        query = query.where(SKU.product_id == product_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    skus = result.scalars().all()
    return skus


@router.get("/{sku_id}", response_model=SKUSchema, summary="获取特定SKU详情")
async def get_sku(
        sku_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定SKU详情
    """
    query = select(SKU).where(SKU.id == sku_id)
    query = query.options(selectinload(SKU.attribute_values))
    result = await db.execute(query)
    sku = result.scalars().first()

    if sku is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU不存在")

    return sku


@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED, summary="创建SKU")
async def create_sku(
        sku_create: SKUCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新SKU
    """
    # 检查商品是否存在
    product_result = await db.execute(select(Product).where(Product.id == sku_create.product_id))
    product = product_result.scalars().first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 检查属性值是否存在
    attribute_value_ids = sku_create.attribute_value_ids
    attribute_values_result = await db.execute(
        select(AttributeValue).where(AttributeValue.id.in_(attribute_value_ids))
    )
    attribute_values = attribute_values_result.scalars().all()
    if len(attribute_values) != len(attribute_value_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部分属性值不存在")

    # 创建SKU对象（不包含属性值关联）
    sku_data = sku_create.model_dump(exclude={"attribute_value_ids"})
    db_sku = SKU(**sku_data)

    # 添加属性值关联
    db_sku.attribute_values = attribute_values

    db.add(db_sku)
    await db.commit()
    await db.refresh(db_sku)

    # 预加载attribute_values关系
    result = await db.execute(
        select(SKU)
        .options(selectinload(SKU.attribute_values))
        .where(SKU.id == db_sku.id)
    )
    db_sku_with_values = result.scalars().first()

    return db_sku_with_values


@router.put("/{sku_id}", response_model=SKUSchema, summary="更新SKU信息")
async def update_sku(
        sku_id: int,
        sku_update: SKUUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新SKU
    """
    # 查询SKU是否存在
    result = await db.execute(select(SKU).where(SKU.id == sku_id))
    db_sku = result.scalars().first()
    if db_sku is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU不存在")

    # 如果更新了商品ID，检查新商品是否存在
    update_data = sku_update.model_dump(exclude_unset=True)
    if "product_id" in update_data and update_data["product_id"] != db_sku.product_id:
        product_result = await db.execute(
            select(Product).where(Product.id == update_data["product_id"])
        )
        product = product_result.scalars().first()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 更新属性值关联
    if "attribute_value_ids" in update_data:
        attribute_value_ids = update_data.pop("attribute_value_ids")
        attribute_values_result = await db.execute(
            select(AttributeValue).where(AttributeValue.id.in_(attribute_value_ids))
        )
        attribute_values = attribute_values_result.scalars().all()
        if len(attribute_values) != len(attribute_value_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部分属性值不存在")

        db_sku.attribute_values = attribute_values

    # 更新SKU字段
    for key, value in update_data.items():
        setattr(db_sku, key, value)

    await db.commit()
    await db.refresh(db_sku)

    # 预加载attribute_values关系
    result = await db.execute(
        select(SKU)
        .options(selectinload(SKU.attribute_values))
        .where(SKU.id == sku_id)
    )
    db_sku_with_values = result.scalars().first()

    return db_sku_with_values


@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除SKU")
async def delete_sku(
        sku_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除SKU
    """
    # 查询SKU是否存在
    result = await db.execute(select(SKU).where(SKU.id == sku_id))
    sku = result.scalars().first()
    if sku is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU不存在")

    # 删除SKU
    await db.delete(sku)
    await db.commit()

    return None


@router.post("/batch-delete", status_code=status.HTTP_204_NO_CONTENT, summary="批量删除SKU")
async def batch_delete_skus(
        sku_ids: List[int],
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    批量删除SKU
    """
    if not sku_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU ID列表不能为空"
        )

    # 检查所有SKU是否存在
    skus_result = await db.execute(
        select(SKU).where(SKU.id.in_(sku_ids))
    )
    skus = skus_result.scalars().all()

    found_ids = {sku.id for sku in skus}
    missing_ids = set(sku_ids) - found_ids

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"以下SKU ID不存在: {', '.join(map(str, missing_ids))}"
        )

    # 删除所有找到的SKU
    for sku in skus:
        await db.delete(sku)

    await db.commit()

    return None


@router.post("/generate", response_model=List[SKUSchema], status_code=status.HTTP_201_CREATED, summary="根据属性组合批量生成SKU")
async def generate_skus(
        request: GenerateSKUsRequest,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    根据属性组合批量生成SKU
    """
    # 检查商品是否存在
    product_result = await db.execute(
        select(Product).where(Product.id == request.product_id)
    )
    product = product_result.scalars().first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 检查属性是否存在且是用于SKU生成的属性
    attributes_result = await db.execute(
        select(Attribute)
        .where(Attribute.id.in_(request.attribute_ids))
        .where(Attribute.is_sku == True)
    )
    attributes = attributes_result.scalars().all()
    if len(attributes) != len(request.attribute_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分属性不存在或不是用于SKU生成的属性"
        )

    # 获取每个属性的属性值
    attribute_values_by_attribute = {}
    for attribute in attributes:
        values_result = await db.execute(
            select(AttributeValue).where(AttributeValue.attribute_id == attribute.id)
        )
        values = values_result.scalars().all()
        if not values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"属性 '{attribute.name}' 没有属性值，无法生成SKU"
            )
        attribute_values_by_attribute[attribute.id] = values

    # 生成所有可能的属性值组合
    attribute_value_combinations = list(itertools_product(*attribute_values_by_attribute.values()))

    # 获取商品现有的SKU名称
    existing_skus_result = await db.execute(
        select(SKU.name).where(SKU.product_id == product.id)
    )
    existing_sku_names = {sku_name for sku_name, in existing_skus_result}

    # 获取商品现有的SKU编码
    existing_codes_result = await db.execute(
        select(SKU.code).where(SKU.product_id == product.id)
    )
    existing_codes = {code for code, in existing_codes_result if code}

    # 获取商品的最大SKU编码数字后缀
    max_code_suffix = 0
    product_code_prefix = f"P{product.id}-"
    for code in existing_codes:
        if code and code.startswith(product_code_prefix):
            try:
                suffix = int(code[len(product_code_prefix):])
                max_code_suffix = max(max_code_suffix, suffix)
            except ValueError:
                continue

    # 创建新SKU
    created_skus = []

    for combination in attribute_value_combinations:
        # 构建SKU名称
        sku_name = f"{product.name}-" + "-".join([value.value for value in combination])

        # 检查是否已存在相同名称的SKU
        if sku_name in existing_sku_names:
            continue

        # 生成SKU编码
        max_code_suffix += 1
        sku_code = f"{product_code_prefix}{max_code_suffix:04d}"

        # 创建新SKU
        new_sku = SKU(
            product_id=product.id,
            code=sku_code,
            name=sku_name,
            price=product.price + request.price_increment,
            stock=request.stock_initial,
            is_active=True,
        )

        # 添加属性值关联
        new_sku.attribute_values = list(combination)

        db.add(new_sku)
        created_skus.append(new_sku)
        # 添加到已存在的SKU名称集合中，避免在同一批次中创建重复的SKU
        existing_sku_names.add(sku_name)

    await db.commit()

    # 获取所有创建的SKU的ID
    sku_ids = [sku.id for sku in created_skus]

    # 预加载attribute_values关系
    if sku_ids:
        result = await db.execute(
            select(SKU)
            .options(selectinload(SKU.attribute_values))
            .where(SKU.id.in_(sku_ids))
        )
        skus_with_values = result.scalars().all()
        return skus_with_values

    return []
