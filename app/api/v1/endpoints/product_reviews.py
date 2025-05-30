from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user, has_permission
from app.models.product import Product
from app.models.product_review import ProductReview, ReviewReply
from app.models.rbac import Role
from app.models.user import User
from app.schemas.product_review import (
    ProductReviewCreate,
    ProductReviewUpdate,
    ProductReview as ProductReviewSchema,
    ReviewReplyCreate,
    ReviewReplyUpdate,
    ReviewReply as ReviewReplySchema,
    ProductReviewStats,
)

router = APIRouter()


@router.get("/", response_model=List[ProductReviewSchema])
async def list_reviews(
        product_id: Optional[int] = None,
        user_id: Optional[int] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        verified_only: bool = False,
        sort_by: Literal["created_at", "rating"] = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    获取商品评价列表，支持多种筛选条件和排序选项
    """
    # 预加载当前用户的角色和权限，避免懒加载问题
    if user_id and user_id != current_user.id:
        # 查询用户的角色和权限
        user_query = select(User).where(User.id == current_user.id).options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
        user_result = await db.execute(user_query)
        user_with_roles = user_result.scalar_one_or_none()

        # 检查权限
        is_admin = any(role.name in ["超级管理员", "商品管理员"] for role in user_with_roles.roles)
        has_manage_all = any(
            perm.code == "review:manage_all" for role in user_with_roles.roles for perm in role.permissions)

        if not (is_admin or has_manage_all):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看其他用户的评价")

    query = select(ProductReview).options(selectinload(ProductReview.replies))

    # 应用筛选条件
    if product_id:
        query = query.filter(ProductReview.product_id == product_id)
    if user_id:
        query = query.filter(ProductReview.user_id == user_id)
    if min_rating:
        query = query.filter(ProductReview.rating >= min_rating)
    if max_rating:
        query = query.filter(ProductReview.rating <= max_rating)
    if verified_only:
        query = query.filter(ProductReview.is_verified_purchase == True)

    # 应用排序
    if sort_by == "created_at":
        order_column = ProductReview.created_at
    elif sort_by == "rating":
        order_column = ProductReview.rating
    else:
        order_column = ProductReview.created_at

    if sort_order == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    reviews = result.scalars().all()

    # 处理匿名评价和用户名
    processed_reviews = []
    for review in reviews:
        if review.is_anonymous:
            # 如果是匿名评价，不返回用户信息
            review.username = "匿名用户"
        else:
            # 获取用户名
            user_result = await db.execute(select(User.username).where(User.id == review.user_id))
            username = user_result.scalar_one_or_none()
            review.username = username

        # 处理回复的用户名
        reply_list = []
        for reply in review.replies:
            user_result = await db.execute(select(User.username).where(User.id == reply.user_id))
            username = user_result.scalar_one_or_none()
            reply.username = username
            # 确保回复对象的review引用为None，避免循环引用
            reply.review = None
            reply_list.append(reply)

        # 替换原始replies列表
        review.replies = reply_list
        processed_reviews.append(review)

    return processed_reviews


@router.get("/stats", response_model=ProductReviewStats)
async def get_review_stats(
        product_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("review:stats")),
):
    """
    获取商品评价统计信息
    """
    # 检查商品是否存在
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 获取总评价数
    total_result = await db.execute(
        select(func.count()).where(ProductReview.product_id == product_id)
    )
    total_reviews = total_result.scalar_one()

    # 获取平均评分
    if total_reviews > 0:
        avg_result = await db.execute(
            select(func.avg(ProductReview.rating)).where(ProductReview.product_id == product_id)
        )
        average_rating = round(avg_result.scalar_one(), 1)
    else:
        average_rating = 0.0

    # 获取评分分布
    distribution = {}
    for rating in range(1, 6):
        count_result = await db.execute(
            select(func.count()).where(
                and_(
                    ProductReview.product_id == product_id,
                    ProductReview.rating == rating
                )
            )
        )
        distribution[rating] = count_result.scalar_one()

    return ProductReviewStats(
        product_id=product_id,
        average_rating=average_rating,
        total_reviews=total_reviews,
        rating_distribution=distribution
    )


@router.get("/{review_id}", response_model=ProductReviewSchema)
async def get_review(
        review_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("review:read")),
):
    """
    获取单个评价详情
    """
    query = select(ProductReview).options(selectinload(ProductReview.replies)).where(ProductReview.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在")

    # 处理匿名评价
    if review.is_anonymous:
        review.username = "匿名用户"
    else:
        # 获取用户名
        user_result = await db.execute(select(User.username).where(User.id == review.user_id))
        username = user_result.scalar_one_or_none()
        review.username = username

    # 处理回复的用户名
    for reply in review.replies:
        user_result = await db.execute(select(User.username).where(User.id == reply.user_id))
        username = user_result.scalar_one_or_none()
        reply.username = username

    return review


@router.post("/", response_model=ProductReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
        review: ProductReviewCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(has_permission("review:create")),
):
    """
    创建商品评价
    """
    # 检查商品是否存在
    product_result = await db.execute(select(Product).where(Product.id == review.product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    # 检查用户是否已经评价过该商品
    existing_review = await db.execute(
        select(ProductReview).where(
            and_(
                ProductReview.product_id == review.product_id,
                ProductReview.user_id == current_user.id
            )
        )
    )
    if existing_review.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您已经评价过该商品"
        )

    # 创建评价
    db_review = ProductReview(
        user_id=current_user.id,
        product_id=review.product_id,
        order_id=review.order_id,
        rating=review.rating,
        content=review.content,
        images=review.images,
        is_anonymous=review.is_anonymous,
        # 如果有订单ID，则标记为已验证购买
        is_verified_purchase=review.order_id is not None
    )

    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    # 使用selectinload预加载replies关系，避免懒加载问题
    query = select(ProductReview).options(selectinload(ProductReview.replies)).where(ProductReview.id == db_review.id)
    result = await db.execute(query)
    review_with_replies = result.scalar_one_or_none()

    # 设置用户名
    if review_with_replies.is_anonymous:
        review_with_replies.username = "匿名用户"
    else:
        review_with_replies.username = current_user.username

    return review_with_replies


@router.put("/{review_id}", response_model=ProductReviewSchema)
async def update_review(
        review_id: int,
        review_update: ProductReviewUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    更新商品评价
    """
    # 获取评价
    result = await db.execute(
        select(ProductReview).options(selectinload(ProductReview.replies)).where(ProductReview.id == review_id)
    )
    db_review = result.scalar_one_or_none()

    if not db_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在")

    # 预加载当前用户的角色和权限，避免懒加载问题
    user_query = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles).selectinload(Role.permissions)
    )
    user_result = await db.execute(user_query)
    user_with_roles = user_result.scalar_one_or_none()

    # 检查用户是否有更新评价权限
    has_update_permission = any(
        perm.code == "review:update" for role in user_with_roles.roles for perm in role.permissions
    )

    if not has_update_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权更新评价")

    # 检查权限
    has_manage_all = any(
        perm.code == "review:manage_all" for role in user_with_roles.roles for perm in role.permissions)

    if db_review.user_id != current_user.id and not has_manage_all:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权更新此评价")

    # 更新评价
    if review_update.rating is not None:
        db_review.rating = review_update.rating
    if review_update.content is not None:
        db_review.content = review_update.content
    if review_update.images is not None:
        db_review.images = review_update.images
    if review_update.is_anonymous is not None:
        db_review.is_anonymous = review_update.is_anonymous

    await db.commit()
    await db.refresh(db_review)

    # 设置用户名
    if db_review.is_anonymous:
        db_review.username = "匿名用户"
    else:
        db_review.username = current_user.username

    # 处理回复的用户名
    for reply in db_review.replies:
        user_result = await db.execute(select(User.username).where(User.id == reply.user_id))
        username = user_result.scalar_one_or_none()
        reply.username = username

    return db_review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
        review_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    删除商品评价
    """
    # 获取评价
    result = await db.execute(select(ProductReview).where(ProductReview.id == review_id))
    db_review = result.scalar_one_or_none()

    if not db_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在")

    # 预加载当前用户的角色和权限，避免懒加载问题
    user_query = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles).selectinload(Role.permissions)
    )
    user_result = await db.execute(user_query)
    user_with_roles = user_result.scalar_one_or_none()

    # 检查权限（用户只能删除自己的评价，有管理权限的用户可以删除任何评价）
    has_manage_all = any(
        perm.code == "review:manage_all" for role in user_with_roles.roles for perm in role.permissions)

    if db_review.user_id != current_user.id and not has_manage_all:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此评价")

    # 删除评价
    await db.delete(db_review)
    await db.commit()

    return None


@router.post("/{review_id}/replies", response_model=ReviewReplySchema, status_code=status.HTTP_201_CREATED)
async def create_reply(
        review_id: int,
        reply: ReviewReplyCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    创建评价回复
    """
    # 检查评价是否存在
    review_result = await db.execute(select(ProductReview).where(ProductReview.id == review_id))
    review = review_result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在")

    # 预加载当前用户的角色和权限，避免懒加载问题
    user_query = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles).selectinload(Role.permissions)
    )
    user_result = await db.execute(user_query)
    user_with_roles = user_result.scalar_one_or_none()

    # 检查用户是否有回复权限
    has_reply_permission = any(
        perm.code == "review:reply" for role in user_with_roles.roles for perm in role.permissions
    )

    if not has_reply_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权回复评价")

    # 检查是否是商家回复（通过角色判断）
    is_merchant = False
    for role in user_with_roles.roles:
        if role.name in ["超级管理员", "merchant", "商品管理员"]:
            is_merchant = True
            break

    # 创建回复
    db_reply = ReviewReply(
        review_id=review_id,
        user_id=current_user.id,
        content=reply.content,
        is_merchant=is_merchant
    )

    db.add(db_reply)
    await db.commit()
    await db.refresh(db_reply)

    # 设置用户名
    db_reply.username = current_user.username

    # 确保review属性不会被异步加载
    db_reply.review = None

    return db_reply


@router.put("/replies/{reply_id}", response_model=ReviewReplySchema)
async def update_reply(
        reply_id: int,
        reply_update: ReviewReplyUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    更新评价回复
    """
    # 获取回复
    result = await db.execute(select(ReviewReply).where(ReviewReply.id == reply_id))
    db_reply = result.scalar_one_or_none()

    if not db_reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回复不存在")

    # 预加载当前用户的角色和权限，避免懒加载问题
    user_query = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles).selectinload(Role.permissions)
    )
    user_result = await db.execute(user_query)
    user_with_roles = user_result.scalar_one_or_none()

    # 检查权限
    has_manage_all = any(
        perm.code == "review:manage_all" for role in user_with_roles.roles for perm in role.permissions)

    if db_reply.user_id != current_user.id and not has_manage_all:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权更新此回复")

    # 更新回复
    if reply_update.content is not None:
        db_reply.content = reply_update.content

    await db.commit()
    await db.refresh(db_reply)

    # 设置用户名
    db_reply.username = current_user.username

    # 确保review属性不会被异步加载
    db_reply.review = None

    return db_reply


@router.delete("/replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply(
        reply_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    删除评价回复
    """
    # 获取回复
    result = await db.execute(select(ReviewReply).where(ReviewReply.id == reply_id))
    db_reply = result.scalar_one_or_none()

    if not db_reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回复不存在")

    # 预加载当前用户的角色和权限，避免懒加载问题
    user_query = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles).selectinload(Role.permissions)
    )
    user_result = await db.execute(user_query)
    user_with_roles = user_result.scalar_one_or_none()

    # 检查权限（用户只能删除自己的回复，有管理权限的用户可以删除任何回复）
    has_manage_all = any(
        perm.code == "review:manage_all" for role in user_with_roles.roles for perm in role.permissions)

    if db_reply.user_id != current_user.id and not has_manage_all:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此回复")

    # 删除回复
    await db.delete(db_reply)
    await db.commit()

    return None
