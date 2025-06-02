from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product import Product, Tag, Category
from app.models.user import User
from app.schemas.product import (
    Product as ProductSchema,
    ProductCreate,
    ProductUpdate,
)
from app.utils.product_indexer import index_single_product, update_product_in_index, delete_product_from_index

router = APIRouter()


@router.get("/", response_model=List[ProductSchema])
async def list_products(
        skip: int = 0,
        limit: int = 100,
        category_id: Optional[int] = None,
        tag_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
):
    """
    获取商品列表，支持多种筛选条件
    """
    query = select(Product)

    # 应用筛选条件
    if category_id is not None:
        # 筛选特定分类的商品
        query = query.where(Product.category_id == category_id)

    if tag_id is not None:
        # 筛选包含特定标签的商品
        query = query.join(Product.tags).where(Tag.id == tag_id)

    if is_active is not None:
        # 筛选上架的商品
        query = query.where(Product.is_active == is_active)

    if search:
        # 简单的搜索功能，匹配商品名称或描述
        search_term = f"%{search}%"
        query = query.where(
            (Product.name.ilike(search_term)) |
            (Product.description.ilike(search_term))
        )

    # 预加载关联数据
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags)
    )

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    products = result.scalars().all()

    return products


@router.get("/{product_id}", response_model=ProductSchema)
async def get_product(
        product_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定商品详情
    """
    query = select(Product).where(Product.id == product_id)
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags)
    )

    result = await db.execute(query)
    product = result.scalars().first()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    return product


@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
        product: ProductCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新商品
    """
    # 检查分类是否存在
    category_result = await db.execute(select(Category).where(Category.id == product.category_id))
    category = category_result.scalars().first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定的分类不存在",
        )

    # 创建商品基本信息
    product_data = product.model_dump(exclude={"tag_ids"})
    db_product = Product(**product_data)

    # 如果提供了标签ID，添加标签关联
    if product.tag_ids:
        for tag_id in product.tag_ids:
            tag_result = await db.execute(select(Tag).where(Tag.id == tag_id))
            tag = tag_result.scalars().first()
            if tag:
                db_product.tags.append(tag)
            else:
                # 可以选择忽略不存在的标签，或者抛出错误
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"标签ID {tag_id} 不存在",
                )

    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)

    # 重新查询以获取完整的关联数据
    query = select(Product).where(Product.id == db_product.id)
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags)
    )
    result = await db.execute(query)
    db_product = result.scalars().first()

    # 将新商品添加到Elasticsearch索引
    try:
        await index_single_product(db, int(db_product.id))
    except Exception as e:
        # 记录错误但不影响API响应
        print(f"索引商品时出错: {str(e)}")

    return db_product


@router.put("/{product_id}", response_model=ProductSchema)
async def update_product(
        product_id: int,
        product_update: ProductUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新商品
    """
    # 查询商品是否存在
    query = select(Product).where(Product.id == product_id)
    query = query.options(selectinload(Product.tags))
    result = await db.execute(query)
    db_product = result.scalars().first()

    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 如果更新了分类ID，检查分类是否存在
    if product_update.category_id is not None:
        category_result = await db.execute(select(Category).where(Category.id == product_update.category_id))
        category = category_result.scalars().first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指定的分类不存在",
            )

    # 更新商品基本字段
    update_data = product_update.model_dump(exclude={"tag_ids"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)

    # 如果提供了标签ID，更新标签关联
    if product_update.tag_ids is not None:
        # 清除现有标签
        db_product.tags = []

        # 添加新标签
        for tag_id in product_update.tag_ids:
            tag_result = await db.execute(select(Tag).where(Tag.id == tag_id))
            tag = tag_result.scalars().first()
            if tag:
                db_product.tags.append(tag)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"标签ID {tag_id} 不存在",
                )

    await db.commit()
    await db.refresh(db_product)

    # 重新查询以获取完整的关联数据
    query = select(Product).where(Product.id == product_id)
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags)
    )
    result = await db.execute(query)
    db_product = result.scalars().first()

    # 更新Elasticsearch索引中的商品
    try:
        await update_product_in_index(db, product_id)
    except Exception as e:
        # 记录错误但不影响API响应
        print(f"更新商品索引时出错: {str(e)}")

    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
        product_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除商品
    """
    # 查询商品是否存在
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalars().first()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 从Elasticsearch索引中删除商品
    try:
        await delete_product_from_index(product_id)
    except Exception as e:
        # 记录错误但不影响API响应
        print(f"从索引中删除商品时出错: {str(e)}")

    # 删除商品
    await db.delete(product)
    await db.commit()

    return None
