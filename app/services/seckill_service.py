from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import get_redis_pool
from app.models.seckill import SeckillActivity, SeckillProduct, SeckillActivityStatus
from app.schemas.seckill import (
    SeckillActivityCreate,
    SeckillActivityUpdate,
    SeckillProductCreate,
    SeckillProductUpdate, SeckillOrderCreate, SeckillOrderResponse, SeckillOrderStatus,
)
from app.utils.redis_lock import RedisLock
import json
import uuid
from datetime import datetime, timezone


class SeckillService:
    def _check_activity_is_modifiable(self, activity: SeckillActivity):  # noqa
        """辅助函数，检查活动是否允许修改"""
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

    async def get_public_activities(  # noqa
            self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[SeckillActivity]:
        """
        获取公开的秒杀活动列表 (状态为 PENDING 或 ACTIVE)
        """
        result = await db.execute(
            select(SeckillActivity)
            .where(
                SeckillActivity.status.in_(
                    [SeckillActivityStatus.PENDING, SeckillActivityStatus.ACTIVE]
                )
            )
            .offset(skip)
            .limit(limit)
            .order_by(SeckillActivity.start_time.asc())
        )
        return list(result.scalars().all())

    async def get_public_activity(  # noqa
            self, db: AsyncSession, activity_id: int
    ) -> Optional[SeckillActivity]:
        """
        获取单个公开的秒杀活动详情 (状态为 PENDING 或 ACTIVE)
        """
        result = await db.execute(
            select(SeckillActivity)
            .where(
                SeckillActivity.id == activity_id,
                SeckillActivity.status.in_(
                    [SeckillActivityStatus.PENDING, SeckillActivityStatus.ACTIVE]
                ),
            )
            .options(selectinload(SeckillActivity.products))
        )
        return result.scalars().first()

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
        使用Lua脚本将秒杀活动及其商品库存预热到Redis中，确保操作的原子性
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
            local sku_map_key = "seckill:activity:" .. activity_id .. ":sku_map"

            -- 1. Clean up old keys for this activity
            local old_product_ids = redis.call("SMEMBERS", activity_products_key)
            for i, old_prod_id in ipairs(old_product_ids) do
                redis.call("DEL", "seckill:stock:" .. old_prod_id)
                redis.call("DEL", "seckill:product:" .. old_prod_id)
            end
            redis.call("DEL", activity_products_key)
            redis.call("DEL", sku_map_key) -- 清理旧的SKU映射

            -- 2. Load new data if any products exist
            if #products == 0 then
                return 0
            end

            for i, product in ipairs(products) do
                local product_id = product["id"]
                local sku_id = product["sku_id"]
                local stock_key = "seckill:stock:" .. product_id
                local product_info_key = "seckill:product:" .. product_id

                redis.call("SET", stock_key, product["seckill_stock"])
                redis.call("HSET", product_info_key,
                    "activity_id", activity_id,
                    "sku_id", sku_id,
                    "seckill_price", product["seckill_price"],
                    "purchase_limit", product["purchase_limit"],
                    "start_time", start_time,
                    "end_time", end_time
                )
                redis.call("SADD", activity_products_key, product_id)
                redis.call("HSET", sku_map_key, sku_id, product_id) -- 添加SKU到秒杀商品ID的映射
            end

            return #products
            """

            await redis.eval(
                lua_script,
                1,
                activity_id,
                json.dumps(products_data),
                db_activity.start_time.astimezone(timezone.utc).isoformat(),
                db_activity.end_time.astimezone(timezone.utc).isoformat(),
            )

            # 预热成功后，立即将活动状态更新为 ACTIVE，防止数据不一致
            db_activity.status = SeckillActivityStatus.ACTIVE
            db.add(db_activity)
            await db.commit()

        finally:
            await lock.release()

        return True

    async def create_seckill_order(self, activity_id: int, user_id: int,  # noqa
                                   order_in: SeckillOrderCreate) -> SeckillOrderResponse:
        """
        处理秒杀下单请求，使用Lua脚本保证原子性，成功后发送异步任务到Celery
        返回一个唯一的请求ID用于后续查询
        """
        redis = await get_redis_pool()
        request_id = str(uuid.uuid4())

        lua_script = """
        -- KEYS[1]: sku_map_key (seckill:activity:{activity_id}:sku_map)
        -- KEYS[2]: user_purchase_key (seckill:purchase:user:{user_id}:activity:{activity_id})
        -- ARGV[1]: sku_id
        -- ARGV[2]: quantity
        -- ARGV[3]: current_time (ISO format string)

        -- 1. 查找秒杀商品ID
        local sku_id = ARGV[1]
        local quantity = tonumber(ARGV[2])
        local product_id = redis.call('HGET', KEYS[1], sku_id)
        if not product_id then
            return {-1, 'SKU not in this seckill activity'}
        end

        -- 2. 获取商品信息和库存
        local product_info_key = "seckill:product:" .. product_id
        local stock_key = "seckill:stock:" .. product_id
        local product_info = redis.call('HGETALL', product_info_key)

        -- 3. 校验活动时间
        local start_time_str = product_info[10] -- 'start_time' is the 10th value in HGETALL result
        local end_time_str = product_info[12]   -- 'end_time' is the 12th
        local current_time = ARGV[3]
        if current_time < start_time_str then
            return {-2, 'Seckill has not started yet'}
        end
        if current_time > end_time_str then
            return {-3, 'Seckill has already ended'}
        end

        -- 4. 校验库存
        local stock = tonumber(redis.call('GET', stock_key))
        if stock < quantity then
            return {-4, 'Insufficient stock'}
        end

        -- 5. 校验用户限购
        local purchase_limit = tonumber(product_info[8]) -- 'purchase_limit' is the 8th value
        local user_purchased_count = tonumber(redis.call('HGET', KEYS[2], product_id) or 0)
        if (user_purchased_count + quantity) > purchase_limit then
            return {-5, 'Purchase limit exceeded for this product'}
        end

        -- 6. 原子化扣减库存和记录用户购买量
        redis.call('DECRBY', stock_key, quantity)
        redis.call('HINCRBY', KEYS[2], product_id, quantity)

        -- 7. 返回成功信息
        local seckill_price = product_info[6] -- 'seckill_price' is the 6th value
        return {1, product_id, seckill_price}
        """

        sku_map_key = f"seckill:activity:{activity_id}:sku_map"
        user_purchase_key = f"seckill:purchase:user:{user_id}:activity:{activity_id}"
        current_time_iso = datetime.now(timezone.utc).isoformat()

        try:
            result = await redis.eval(
                lua_script,
                2,
                sku_map_key,
                user_purchase_key,
                order_in.sku_id,
                order_in.quantity,
                current_time_iso
            )
        except Exception as e:
            # Redis脚本执行失败，通常是连接问题或语法错误
            raise ValueError(f"Error executing Redis script: {e}")

        status_code = result[0]
        if status_code != 1:
            # 根据脚本返回的错误码，抛出业务异常
            raise ValueError(result[1])

        # Lua脚本执行成功，设置初始状态并发送消息到队列
        product_id = result[1]
        seckill_price = result[2]

        initial_status = {
            "status": "PROCESSING",
            "message": "您的请求正在处理中...",
            "user_id": user_id
        }
        status_key = f"seckill:request:{request_id}"
        await redis.set(status_key, json.dumps(initial_status), ex=600)  # 10分钟过期

        message_body = {
            "request_id": request_id,
            "user_id": user_id,
            "seckill_product_id": product_id,
            "price": seckill_price,
            "order_details": order_in.model_dump()
        }

        celery_app.send_task(
            settings.CELERY_TASK_CREATE_SECKILL_ORDER,
            args=[message_body]
        )

        return SeckillOrderResponse(request_id=request_id)

    async def get_seckill_order_status(self, request_id: str, user_id: int) -> Optional[SeckillOrderStatus]:  # noqa
        """
        根据请求ID查询秒杀订单的处理状态
        """
        redis = await get_redis_pool()
        status_key = f"seckill:request:{request_id}"
        data = await redis.get(status_key)

        if not data:
            return None

        status_data = json.loads(data)

        # 安全校验：确保用户只能查询自己的请求
        if status_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")

        return SeckillOrderStatus.model_validate(status_data)

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
