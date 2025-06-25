from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product import Category, Product
from app.models.user import User
from app.schemas.product import (
    Category as CategorySchema,
    CategoryCreate,
    CategoryUpdate,
    CategoryTree,
)

router = APIRouter()


@router.get("/", response_model=List[CategorySchema], summary="获取分类列表")
async def list_categories(
        skip: int = 0,
        limit: int = 100,
        parent_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db),
):
    """
    获取分类列表，可以通过parent_id筛选特定父分类下的子分类
    """
    query = select(Category).offset(skip).limit(limit)

    # 如果指定了parent_id，则只查询该父分类下的子分类
    if parent_id is not None:
        query = query.where(Category.parent_id == parent_id)
    else:
        # 否则默认查询顶级分类（parent_id为空的分类）
        query = query.where(Category.parent_id.is_(None))

    # 预加载父分类和子分类
    query = query.options(
        selectinload(Category.parent),
        selectinload(Category.children).selectinload(Category.children).selectinload(Category.children)
    )

    result = await db.execute(query)
    categories = result.scalars().all()

    return categories


@router.get("/tree", response_model=List[CategoryTree], summary="获取完整的分类树结构")
async def get_category_tree(db: AsyncSession = Depends(get_db)):
    """
    获取完整的分类树结构
    """
    # 只查询顶级分类（parent_id为空的分类）
    query = select(Category).where(Category.parent_id.is_(None))

    # 递归预加载所有子分类
    query = query.options(
        selectinload(Category.children).selectinload(Category.children).selectinload(Category.children)
    )

    result = await db.execute(query)
    categories = result.scalars().all()

    return categories


@router.get("/{category_id}", response_model=CategorySchema, summary="获取特定分类详情")
async def get_category(
        category_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定分类详情
    """
    query = select(Category).where(Category.id == category_id)
    query = query.options(
        selectinload(Category.parent),
        selectinload(Category.children).selectinload(Category.children).selectinload(Category.children)
    )

    result = await db.execute(query)
    category = result.scalars().first()

    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")

    return category


@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED, summary="创建分类")
async def create_category(
        category: CategoryCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新分类
    """
    # 如果指定了父分类，检查父分类是否存在
    if category.parent_id is not None:
        parent_result = await db.execute(select(Category).where(Category.id == category.parent_id))
        parent = parent_result.scalars().first()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父分类不存在",
            )

    # 创建新分类
    db_category = Category(**category.model_dump())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)

    # 重新查询以获取关联数据
    query = select(Category).where(Category.id == db_category.id)
    query = query.options(
        selectinload(Category.parent),
        selectinload(Category.children).selectinload(Category.children).selectinload(Category.children)
    )
    result = await db.execute(query)
    db_category = result.scalars().first()

    return db_category


@router.put("/{category_id}", response_model=CategorySchema, summary="更新分类信息")
async def update_category(
        category_id: int,
        category_update: CategoryUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新分类
    """
    # 查询分类是否存在
    result = await db.execute(select(Category).where(Category.id == category_id))
    db_category = result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")

    # 如果更新了父分类ID，检查父分类是否存在
    if category_update.parent_id is not None and category_update.parent_id != db_category.parent_id:
        # 检查是否将分类设为自己的子分类，这会导致循环引用
        if category_update.parent_id == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将分类设为自己的子分类",
            )

        # 检查父分类是否存在
        parent_result = await db.execute(select(Category).where(Category.id == category_update.parent_id))
        parent = parent_result.scalars().first()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父分类不存在",
            )

        # 检查是否将分类设为其子分类的子分类，这会导致循环引用
        # 获取所有子分类ID
        child_ids = await get_all_child_ids(db, category_id)
        if category_update.parent_id in child_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将分类设为其子分类的子分类",
            )

    # 更新分类字段
    update_data = category_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)

    await db.commit()
    await db.refresh(db_category)

    # 重新查询以获取关联数据
    query = select(Category).where(Category.id == category_id)
    query = query.options(
        selectinload(Category.parent),
        selectinload(Category.children).selectinload(Category.children).selectinload(Category.children)
    )
    result = await db.execute(query)
    db_category = result.scalars().first()

    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除分类")
async def delete_category(
        category_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除分类
    """
    # 查询分类是否存在
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalars().first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")

    # 检查分类下是否有商品
    product_count_result = await db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    product_count = product_count_result.scalar()
    if product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该分类下存在商品，无法删除",
        )

    # 删除分类
    await db.delete(category)
    await db.commit()

    return None


async def get_all_child_ids(db: AsyncSession, category_id: int) -> List[int]:
    """
    获取分类的所有子分类ID（递归）
    """
    # 查询直接子分类
    result = await db.execute(select(Category.id).where(Category.parent_id == category_id))
    child_ids = result.scalars().all()

    # 递归查询子分类的子分类
    all_child_ids = list(child_ids)
    for child_id in child_ids:
        sub_child_ids = await get_all_child_ids(db, child_id)
        all_child_ids.extend(sub_child_ids)

    return all_child_ids
