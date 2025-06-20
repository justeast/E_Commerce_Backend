from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis_client import get_redis_pool
from app.models.seckill import SeckillActivity, SeckillProduct, SeckillActivityStatus
from app.schemas.seckill import (
    SeckillActivityCreate,
    SeckillActivityUpdate,
    SeckillProductCreate,
    SeckillProductUpdate,
)
from app.utils.redis_lock import RedisLock
import json


class SeckillService:
    def _check_activity_is_modifiable(self, activity: SeckillActivity):  # noqa
        if activity.status in [SeckillActivityStatus.ACTIVE, SeckillActivityStatus.ENDED]:
            raise HTTPException(
                status_code=400,
                detail=f"活动状态为'{activity.status.value}'，不允许修改。"
            )

    async def get_activity(  # noqa
            self, db: AsyncSession, activity_id: int
    ) -> Optional[SeckillActivity]:
        result = await db.execute(
            select(SeckillActivity)
            .where(SeckillActivity.id == activity_id)
            .options(selectinload(SeckillActivity.products))
        )
        return result.scalars().first()

    async def get_all_activities(  # noqa
            self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[SeckillActivity]:
        result = await db.execute(
            select(SeckillActivity)
            .offset(skip)
            .limit(limit)
            .options(selectinload(SeckillActivity.products))
            .order_by(SeckillActivity.start_time.desc())
        )
        return list(result.scalars().all())

    async def create_activity(  # noqa
            self, db: AsyncSession, activity_in: SeckillActivityCreate
    ) -> SeckillActivity:
        if activity_in.end_time <= activity_in.start_time:
            raise HTTPException(
                status_code=400, detail="End time must be after start time."
            )

        db_activity = SeckillActivity(**activity_in.model_dump())
        db.add(db_activity)
        await db.commit()
        await db.refresh(db_activity, ["products"])
        return db_activity

    async def update_activity(
            self, db: AsyncSession, activity_id: int, activity_in: SeckillActivityUpdate
    ) -> Optional[SeckillActivity]:
        db_activity = await self.get_activity(db, activity_id)
        if not db_activity:
            return None

        self._check_activity_is_modifiable(db_activity)

        update_data = activity_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_activity, field, value)

        db.add(db_activity)
        await db.commit()
        await db.refresh(db_activity, ["products"])
        return db_activity

    async def delete_activity(self, db: AsyncSession, activity_id: int) -> bool:
        db_activity = await self.get_activity(db, activity_id)
        if not db_activity:
            return False

        self._check_activity_is_modifiable(db_activity)

        await db.delete(db_activity)
        await db.commit()
        return True

    async def load_activity_to_redis(self, db: AsyncSession, activity_id: int) -> bool:
        """
        使用Lua脚本将秒杀活动及其商品库存预热到Redis中，确保操作的原子性。
        """
        redis = await get_redis_pool()
        lock = RedisLock(redis, f"seckill:preload:{activity_id}")

        if not await lock.acquire():
            raise HTTPException(
                status_code=409,  # Conflict
                detail="Activity is already being preloaded by another process.",
            )

        try:
            db_activity = await self.get_activity(db, activity_id)
            if not db_activity:
                raise HTTPException(status_code=404, detail="Activity not found")

            if db_activity.status != SeckillActivityStatus.PENDING:
                raise HTTPException(
                    status_code=400,
                    detail=f"活动状态必须为 'PENDING' 才能预热，当前状态: '{db_activity.status.value}'。",
                )

            products_data = [
                {
                    "id": p.id,
                    "sku_id": p.sku_id,
                    "seckill_stock": p.seckill_stock,
                    "seckill_price": str(p.seckill_price),
                    "purchase_limit": p.purchase_limit,
                }
                for p in db_activity.products
            ]

            lua_script = """
            -- KEYS[1]: activity_id
            -- ARGV[1]: JSON string of products array
            -- ARGV[2]: start_time (ISO format string)
            -- ARGV[3]: end_time (ISO format string)

            local activity_id = KEYS[1]
            local products_json = ARGV[1]
            local start_time = ARGV[2]
            local end_time = ARGV[3]
            local products = cjson.decode(products_json)

            local activity_products_key = "seckill:activity:" .. activity_id .. ":products"

            -- 1. Clean up old keys for this activity
            local old_product_ids = redis.call("SMEMBERS", activity_products_key)
            for i, old_prod_id in ipairs(old_product_ids) do
                redis.call("DEL", "seckill:stock:" .. old_prod_id)
                redis.call("DEL", "seckill:product:" .. old_prod_id)
            end
            redis.call("DEL", activity_products_key)

            -- 2. Load new data if any products exist
            if #products == 0 then
                return 0
            end

            for i, product in ipairs(products) do
                local product_id = product["id"]
                local stock_key = "seckill:stock:" .. product_id
                local product_info_key = "seckill:product:" .. product_id

                redis.call("SET", stock_key, product["seckill_stock"])
                redis.call("HSET", product_info_key,
                    "activity_id", activity_id,
                    "sku_id", product["sku_id"],
                    "seckill_price", product["seckill_price"],
                    "purchase_limit", product["purchase_limit"],
                    "start_time", start_time,
                    "end_time", end_time
                )
                redis.call("SADD", activity_products_key, product_id)
            end

            return #products
            """

            await redis.eval(
                lua_script,
                1,
                activity_id,
                json.dumps(products_data),
                db_activity.start_time.isoformat(),
                db_activity.end_time.isoformat(),
            )

            # 预热成功后，立即将活动状态更新为 ACTIVE，防止数据不一致
            db_activity.status = SeckillActivityStatus.ACTIVE
            db.add(db_activity)
            await db.commit()

        finally:
            await lock.release()

        return True

    async def add_product_to_activity(
            self, db: AsyncSession, activity_id: int, product_in: SeckillProductCreate
    ) -> SeckillProduct:
        db_activity = await self.get_activity(db, activity_id)
        if not db_activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        self._check_activity_is_modifiable(db_activity)

        # 检查 SKU 是否已参与此活动
        existing_product = await db.execute(
            select(SeckillProduct).where(
                SeckillProduct.activity_id == activity_id,
                SeckillProduct.sku_id == product_in.sku_id,
            )
        )
        if existing_product.scalars().first():
            raise HTTPException(
                status_code=400, detail="SKU already in this seckill activity"
            )

        db_product = SeckillProduct(**product_in.model_dump(), activity_id=activity_id)
        db.add(db_product)
        await db.commit()
        await db.refresh(db_product)
        return db_product

    async def update_product_in_activity(  # noqa
            self, db: AsyncSession, product_id: int, product_in: SeckillProductUpdate
    ) -> Optional[SeckillProduct]:
        result = await db.execute(
            select(SeckillProduct).where(SeckillProduct.id == product_id).options(selectinload(SeckillProduct.activity))
        )
        db_product = result.scalars().first()

        if not db_product:
            return None

        self._check_activity_is_modifiable(db_product.activity)

        update_data = product_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_product, field, value)

        db.add(db_product)
        await db.commit()
        await db.refresh(db_product)
        return db_product

    async def remove_product_from_activity(  # noqa
            self, db: AsyncSession, product_id: int
    ) -> bool:
        result = await db.execute(
            select(SeckillProduct).where(SeckillProduct.id == product_id).options(selectinload(SeckillProduct.activity))
        )
        db_product = result.scalars().first()

        if not db_product:
            return False

        self._check_activity_is_modifiable(db_product.activity)

        await db.delete(db_product)
        await db.commit()
        return True


seckill_service = SeckillService()
