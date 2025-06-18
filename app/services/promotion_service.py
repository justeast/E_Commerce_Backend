from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion import Promotion
from app.schemas.promotion import PromotionCreate, PromotionUpdate


class PromotionService:
    """促销活动服务类"""

    async def get_promotion_by_id(self, db: AsyncSession, promotion_id: int) -> Optional[Promotion]:  # noqa
        """
        通过ID获取单个促销活动

        :param db: 数据库会话
        :param promotion_id: 促销活动ID
        :return: 促销活动模型对象或None
        """
        query = select(Promotion).where(Promotion.id == promotion_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_promotions(  # noqa
            self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[Promotion]:
        """
        获取促销活动列表（分页）

        :param db: 数据库会话
        :param skip: 跳过的记录数
        :param limit: 返回的记录数
        :return: 促销活动模型对象列表
        """
        query = select(Promotion).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_promotion(self, db: AsyncSession, promotion_in: PromotionCreate) -> Promotion:  # noqa
        """
        创建新的促销活动

        :param db: 数据库会话
        :param promotion_in: 促销活动创建数据模型
        :return: 新创建的促销活动模型对象
        """
        # 将Pydantic模型转换为字典
        promotion_data = promotion_in.model_dump()

        db_promotion = Promotion(**promotion_data)
        db.add(db_promotion)
        await db.commit()
        await db.refresh(db_promotion)
        return db_promotion

    async def update_promotion(  # noqa
            self, db: AsyncSession, promotion: Promotion, promotion_in: PromotionUpdate
    ) -> Promotion:
        """
        更新促销活动信息

        :param db: 数据库会话
        :param promotion: 数据库中已存在的促销活动对象
        :param promotion_in: 待更新的数据
        :return: 更新后的促销活动模型对象
        """
        # 获取更新数据，排除未设置的字段
        update_data = promotion_in.model_dump(exclude_unset=True)

        # 更新模型对象的字段
        for field, value in update_data.items():
            setattr(promotion, field, value)

        db.add(promotion)
        await db.commit()
        await db.refresh(promotion)
        return promotion

    async def delete_promotion(self, db: AsyncSession, promotion_id: int) -> bool:  # noqa
        """
        删除促销活动

        :param db: 数据库会话
        :param promotion_id: 促销活动ID
        :return: 如果删除成功返回True
        """
        query = delete(Promotion).where(Promotion.id == promotion_id)
        result = await db.execute(query)
        await db.commit()
        # result.rowcount > 0 表示有行被删除
        return result.rowcount > 0

    async def get_active_promotions(self, db: AsyncSession) -> List[Promotion]:  # noqa
        """
        获取所有当前有效的促销活动
        一个有效的活动必须是：is_active=True，并且当前时间在start_time和end_time之间

        :param db: 数据库会话
        :return: 有效的促销活动列表
        """
        current_time = datetime.now(timezone.utc)

        query = select(Promotion).where(
            Promotion.is_active == True,
            Promotion.start_time <= current_time,
            Promotion.end_time >= current_time
        )
        result = await db.execute(query)
        return result.scalars().all()


# 实例化服务
promotion_service = PromotionService()
