from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.product import Tag, Product, product_tag
from app.models.user import User
from app.schemas.product import Tag as TagSchema, TagCreate, TagUpdate

router = APIRouter()


@router.get("/", response_model=List[TagSchema])
async def list_tags(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
):
    """
    获取标签列表
    """
    result = await db.execute(select(Tag).offset(skip).limit(limit))
    tags = result.scalars().all()

    return tags


@router.get("/{tag_id}", response_model=TagSchema)
async def get_tag(
        tag_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    获取特定标签详情
    """
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalars().first()

    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    return tag


@router.post("/", response_model=TagSchema, status_code=status.HTTP_201_CREATED)
async def create_tag(
        tag: TagCreate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    创建新标签
    """
    # 检查标签名称是否已存在
    result = await db.execute(select(Tag).where(Tag.name == tag.name))
    existing_tag = result.scalars().first()
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标签名称已存在",
        )

    # 创建新标签
    db_tag = Tag(**tag.model_dump())
    db.add(db_tag)
    await db.commit()
    await db.refresh(db_tag)

    return db_tag


@router.put("/{tag_id}", response_model=TagSchema)
async def update_tag(
        tag_id: int,
        tag_update: TagUpdate,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    更新标签
    """
    # 查询标签是否存在
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    db_tag = result.scalars().first()
    if db_tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    # 如果更新了标签名称，检查名称是否已存在
    if tag_update.name is not None and tag_update.name != db_tag.name:
        name_result = await db.execute(select(Tag).where(Tag.name == tag_update.name))
        existing_tag = name_result.scalars().first()
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签名称已存在",
            )

    # 更新标签字段
    update_data = tag_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tag, key, value)

    await db.commit()
    await db.refresh(db_tag)

    return db_tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
        tag_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage")),
):
    """
    删除标签
    """
    # 查询标签是否存在
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalars().first()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    # 检查标签是否已关联商品
    product_count_result = await db.execute(
        select(func.count(Product.id))
        .join(product_tag)
        .where(product_tag.c.tag_id == tag_id)
    )
    product_count = product_count_result.scalar()
    if product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该标签已关联商品，无法删除",
        )

    # 删除标签
    await db.delete(tag)
    await db.commit()

    return None
