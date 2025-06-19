import logging
import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.coupon import CouponTemplate, UserCoupon, CouponStatus
from app.schemas.coupon import CouponTemplateCreate, CouponTemplateUpdate


# 自定义异常
class CouponException(Exception):
    pass


class CouponTemplateNotFound(CouponException):
    def __init__(self, message="优惠券模板不存在或未激活"):
        self.message = message
        super().__init__(self.message)


class CouponOutOfStock(CouponException):
    def __init__(self, message="优惠券已被领完"):
        self.message = message
        super().__init__(self.message)


class CouponLimitExceeded(CouponException):
    def __init__(self, message="您已达到该优惠券的领取上限"):
        self.message = message
        super().__init__(self.message)


class UserCouponNotFound(CouponException):
    def __init__(self, message="用户优惠券不存在或不属于该用户"):
        self.message = message
        super().__init__(self.message)


class CouponAlreadyUsed(CouponException):
    def __init__(self, message="该优惠券已被使用"):
        self.message = message
        super().__init__(self.message)


class CouponExpired(CouponException):
    def __init__(self, message="该优惠券已过期"):
        self.message = message
        super().__init__(self.message)


class CouponService:
    async def get_template_by_id(self, db: AsyncSession, template_id: int) -> Optional[CouponTemplate]:  # noqa
        """通过ID获取优惠券模板"""
        result = await db.execute(select(CouponTemplate).where(CouponTemplate.id == template_id))
        return result.scalars().first()

    async def get_coupon_templates(  # noqa
            self, db: AsyncSession, page: int, size: int
    ) -> Tuple[List[CouponTemplate], int]:
        """获取所有优惠券模板（分页）"""
        if page < 1:
            page = 1
        if size < 1:
            size = 10

        skip = (page - 1) * size

        count_result = await db.execute(select(func.count(CouponTemplate.id)))
        total = count_result.scalar_one()

        result = await db.execute(
            select(CouponTemplate)
            .order_by(CouponTemplate.created_at.desc())
            .offset(skip)
            .limit(size)
        )
        templates = result.scalars().all()
        return templates, total

    async def create_template(  # noqa
            self, db: AsyncSession, *, template_in: CouponTemplateCreate
    ) -> CouponTemplate:
        """创建新的优惠券模板"""
        db_template = CouponTemplate(**template_in.model_dump())
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        return db_template

    async def update_template(
            self, db: AsyncSession, *, template_id: int, template_in: CouponTemplateUpdate
    ) -> Optional[CouponTemplate]:
        """更新优惠券模板"""
        db_template = await self.get_template_by_id(db, template_id)
        if not db_template:
            return None

        update_data = template_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_template, field, value)

        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        return db_template

    async def delete_coupon_template(self, db: AsyncSession, template_id: int) -> None:
        """
        删除一个优惠券模板
        如果已有用户领取，则不允许删除
        """
        # 检查是否已有用户领取了此模板的优惠券
        user_coupon_check = await db.execute(
            select(UserCoupon.id).where(UserCoupon.coupon_template_id == template_id).limit(1)
        )
        if user_coupon_check.scalar_one_or_none():
            raise ValueError("无法删除该模板，因为已有用户领取了此优惠券。可以尝试将其设置为“未激活”。")

        # 获取模板并删除
        template_to_delete = await self.get_template_by_id(db, template_id)
        if not template_to_delete:
            raise CouponTemplateNotFound("优惠券模板未找到")

        await db.delete(template_to_delete)
        await db.commit()

    async def _generate_coupon_code(self, db: AsyncSession, prefix: Optional[str]) -> str:  # noqa
        """生成唯一的优惠券码"""
        while True:
            code = f"{prefix or 'C'}-{uuid.uuid4().hex[:10].upper()}"
            result = await db.execute(select(UserCoupon).where(UserCoupon.code == code))
            if result.scalars().first() is None:
                return code

    async def claim_coupon(self, db: AsyncSession, *, user_id: int, template_id: int) -> UserCoupon:
        """用户领取优惠券"""
        async with db.begin_nested():  # 使用嵌套事务确保数据一致性
            # 1. 检查模板是否存在且有效
            template = await self.get_template_by_id(db, template_id)
            if not template or not template.is_active:
                raise CouponTemplateNotFound()

            now = datetime.now(timezone.utc)
            if template.valid_from and now < template.valid_from.replace(tzinfo=timezone.utc):
                raise CouponTemplateNotFound("优惠券活动尚未开始")

            if template.valid_to and now > template.valid_to.replace(tzinfo=timezone.utc):
                raise CouponTemplateNotFound("优惠券活动已结束")

            # 2. 检查库存
            if template.total_quantity > 0 and template.issued_quantity >= template.total_quantity:
                raise CouponOutOfStock()

            # 3. 检查用户领取上限
            count_result = await db.execute(
                select(func.count(UserCoupon.id))
                .where(UserCoupon.user_id == user_id, UserCoupon.coupon_template_id == template_id)
            )
            user_claimed_count = count_result.scalar_one()
            if user_claimed_count >= template.usage_limit_per_user:
                raise CouponLimitExceeded()

            # 4. 创建用户优惠券
            new_code = await self._generate_coupon_code(db, template.code_prefix)
            user_coupon = UserCoupon(
                user_id=user_id,
                coupon_template_id=template_id,
                code=new_code,
                status=CouponStatus.UNUSED
            )
            db.add(user_coupon)

            # 5. 更新模板已发行数量
            template.issued_quantity += 1
            db.add(template)

        await db.commit()
        # commit后，原user_coupon对象已过期，直接返回会导致懒加载错误
        # 必须重新查询，并预加载响应模型中需要的关联对象(template)
        result = await db.execute(
            select(UserCoupon)
            .where(UserCoupon.id == user_coupon.id)
            .options(selectinload(UserCoupon.template))
        )
        refreshed_coupon = result.scalar_one()
        return refreshed_coupon

    async def get_user_coupons(  # noqa
            self, db: AsyncSession, *, user_id: int, page: int, size: int, status: Optional[CouponStatus] = None
    ) -> Tuple[List[UserCoupon], int]:
        """获取用户的优惠券列表（分页）"""
        if page < 1:
            page = 1
        if size < 1:
            size = 10
        skip = (page - 1) * size

        # 构建基础查询
        base_query = select(UserCoupon).where(UserCoupon.user_id == user_id)
        if status:
            base_query = base_query.where(UserCoupon.status == status)

        # 查询总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # 查询分页数据
        data_query = (
            base_query
            .options(selectinload(UserCoupon.template))  # 预加载模板信息
            .order_by(UserCoupon.claimed_at.desc())
            .offset(skip)
            .limit(size)
        )

        result = await db.execute(data_query)
        coupons = result.scalars().all()
        return coupons, total

    async def get_user_coupon_by_id(self, db: AsyncSession, coupon_id: int, user_id: Optional[int] = None) -> Optional[
        UserCoupon]:
        """获取单个用户优惠券，可选地验证用户所有权，并预加载模板。"""
        query = select(UserCoupon).options(selectinload(UserCoupon.template)).where(UserCoupon.id == coupon_id)
        if user_id:
            query = query.where(UserCoupon.user_id == user_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def use_coupon(self, db: AsyncSession, *, user_coupon: UserCoupon) -> UserCoupon:  # noqa
        """将优惠券状态标记为“已使用”"""
        if user_coupon.status != CouponStatus.UNUSED:
            raise ValueError("优惠券不是“未使用”状态，无法使用")
        user_coupon.status = CouponStatus.USED
        user_coupon.used_at = datetime.now(timezone.utc)
        db.add(user_coupon)
        await db.flush()
        await db.refresh(user_coupon)
        return user_coupon

    async def return_coupon(self, db: AsyncSession, *, user_coupon_id: int, user_id: int) -> UserCoupon:
        """
        将一个已使用的优惠券返还给用户（例如，当订单被取消时）。
        这是一个原子操作，应该包含在调用它的服务的事务中。
        """
        user_coupon = await self.get_user_coupon_by_id(db, coupon_id=user_coupon_id, user_id=user_id)
        if not user_coupon:
            # 在这种情况下，我们记录一个警告而不是抛出异常，因为订单取消是主要流程
            # 优惠券返还失败不应阻塞订单取消
            logging.warning(f"尝试返还一个不存在或不属于用户 {user_id} 的优惠券 {user_coupon_id}")
            return None  # or raise a specific, non-blocking error

        if user_coupon.status != CouponStatus.USED:
            logging.warning(f"尝试返还一个非“已使用”状态的优惠券 {user_coupon_id}，当前状态: {user_coupon.status}")
            return user_coupon  # 直接返回，不做任何改变

        user_coupon.status = CouponStatus.UNUSED
        user_coupon.used_at = None
        db.add(user_coupon)
        await db.flush()
        await db.refresh(user_coupon)
        return user_coupon


coupon_service = CouponService()
