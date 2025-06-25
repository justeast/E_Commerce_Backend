from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, has_permission, get_current_active_user
from app.models.coupon import CouponStatus
from app.models.user import User
from app.schemas.coupon import (
    CouponTemplate,
    CouponTemplateCreate,
    CouponTemplateUpdate,
    UserCoupon,
    CouponTemplateListResponse, UserCouponListResponse, UserCouponWithTemplate,
)
from app.services.coupon_service import (
    coupon_service,
    CouponException,
    CouponLimitExceeded,
    CouponOutOfStock,
    CouponTemplateNotFound,
)

router = APIRouter()


@router.post("/templates/", response_model=CouponTemplate, status_code=201, summary="创建优惠券模板")
async def create_coupon_template(
        *,
        db: AsyncSession = Depends(get_db),
        template_in: CouponTemplateCreate,
        _: User = Depends(has_permission("product_manage"))  # 需商品管理权限
) -> Any:
    """
    创建优惠券模板
    """
    template = await coupon_service.create_template(db, template_in=template_in)
    return template


@router.get("/templates/", response_model=CouponTemplateListResponse, summary="获取所有优惠券模板")
async def read_coupon_templates(
        db: AsyncSession = Depends(get_db),
        page: int = 1,
        size: int = 10,
        _: User = Depends(has_permission("product_manage"))  # 需商品管理权限
) -> Any:
    """
    获取所有优惠券模板
    """
    templates, total = await coupon_service.get_coupon_templates(db, page=page, size=size)
    return CouponTemplateListResponse(items=templates, total=total)


@router.put("/templates/{template_id}", response_model=CouponTemplate, summary="更新优惠券模板信息")
async def update_coupon_template(
        *,
        db: AsyncSession = Depends(get_db),
        template_id: int,
        template_in: CouponTemplateUpdate,
        _: User = Depends(has_permission("product_manage"))  # 需商品管理权限
) -> Any:
    """
    更新优惠劵模板
    """
    try:
        updated_template = await coupon_service.update_template(
            db, template_id=template_id, template_in=template_in
        )
        if not updated_template:
            raise CouponTemplateNotFound()
        return updated_template
    except CouponTemplateNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CouponException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除优惠券模板")
async def delete_coupon_template(
        template_id: int,
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage"))  # 需商品管理权限
):
    """
    删除一个优惠券模板
    """
    try:
        await coupon_service.delete_coupon_template(db, template_id=template_id)
    except CouponTemplateNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/claim/{template_id}", response_model=UserCoupon, summary="领取优惠券")
async def claim_coupon_for_user(
        *,
        db: AsyncSession = Depends(get_db),
        template_id: int,
        current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    按优惠券的模板ID领取优惠券
    """
    try:
        claimed_coupon = await coupon_service.claim_coupon(
            db=db, user_id=current_user.id, template_id=template_id
        )
        return claimed_coupon
    except (CouponTemplateNotFound, CouponOutOfStock, CouponLimitExceeded) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CouponException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-coupons", response_model=UserCouponListResponse, summary="获取我的优惠券列表")
async def get_my_coupons(
        *,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        coupon_status: Optional[CouponStatus] = Query(None, description="根据状态筛选"),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """获取当前登录用户的所有优惠券，可根据状态筛选，支持分页"""
    coupons, total = await coupon_service.get_user_coupons(
        db, user_id=current_user.id, status=coupon_status, page=page, size=size
    )
    return {"items": coupons, "total": total}


@router.get("/my-coupons/{user_coupon_id}", response_model=UserCouponWithTemplate, summary="获取我的单张优惠券详情")
async def get_my_coupon_by_id(
        *,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        user_coupon_id: int
):
    """获取当前用户拥有的某一张优惠券的详细信息"""
    user_coupon = await coupon_service.get_user_coupon_by_id(
        db, user_id=current_user.id, coupon_id=user_coupon_id
    )
    if not user_coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在或不属于您")
    return user_coupon
