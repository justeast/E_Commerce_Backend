import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis_client import get_redis_pool
from app.models.order import Order, OrderItem, OrderStatusEnum, CartItem
from app.models.product_attribute import SKU, AttributeValue
from app.models.user import User
from app.schemas.order import OrderCreate, OrderCreateFromSelected
from app.services.cart_service import cart_service
from app.services.inventory_service import inventory_service, InsufficientStockException, InventoryLockException
from app.utils.redis_lock import RedisLock


class OrderService:
    async def create_order_from_cart(self, db: AsyncSession, user: User, order_in: OrderCreate) -> Order:  # noqa
        """
        从用户的购物车创建订单，一个包含分布式锁和数据库事务的完整流程
        1. 检查购物车
        2. 为购物车中所有商品加锁
        3. 在一个数据库事务中：
            a. 为所有商品预留库存
            b. 创建订单和订单项
            c. 清空购物车
        4. 释放所有锁
        5. 返回创建的订单
        """
        cart = await cart_service.get_user_cart(db, user)
        if not cart.items:
            raise ValueError("购物车是空的，无法创建订单")

        redis = await get_redis_pool()
        locks: List[RedisLock] = []
        # 预先生成订单号，用于库存预留的关联ID
        order_sn = f"SN{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"

        try:
            # 步骤1: 在事务之外为所有SKU加锁，排序是为了避免不同订单请求之间的死锁
            for item in sorted(cart.items, key=lambda x: x.sku_id):
                lock = RedisLock(redis, f"inventory:sku:{item.sku_id}", expire_seconds=10)
                if not await lock.acquire():
                    raise InventoryLockException(f"SKU {item.sku_id} 正在被其他人抢购，请稍后再试")
                locks.append(lock)

            # 步骤2: 开启数据库事务，执行所有数据库操作
            async with db.begin_nested():
                # 2a. 调用库存服务预留库存
                for item in cart.items:
                    await inventory_service.reserve_stock(
                        db=db,
                        sku_id=item.sku_id,
                        quantity=item.quantity,
                        reference_id=order_sn,
                        reference_type="order_creation",
                        operator_id=user.id,
                        notes=f"为订单 {order_sn} 创建预留库存"
                    )

                # 2b. 获取商品信息并创建订单项
                sku_ids = [item.sku_id for item in cart.items]
                result = await db.execute(
                    select(SKU).options(selectinload(SKU.product)).where(SKU.id.in_(sku_ids))
                )
                skus_map = {sku.id: sku for sku in result.scalars().all()}

                total_amount = sum(item.price * item.quantity for item in cart.items)
                order_items_to_create = [
                    OrderItem(
                        sku_id=item.sku_id,
                        product_name=skus_map[item.sku_id].product.name,
                        sku_name=skus_map[item.sku_id].name,
                        sku_price=item.price,
                        quantity=item.quantity,
                        sku_image_url=skus_map[item.sku_id].image_url,
                    )
                    for item in cart.items
                ]

                # 2c. 创建订单主体
                new_order = Order(
                    order_sn=order_sn,
                    user_id=user.id,
                    total_amount=total_amount,
                    pay_amount=total_amount,  # 实际支付金额，此处暂不考虑优惠
                    status=OrderStatusEnum.PENDING_PAYMENT,
                    receiver_name=order_in.receiver_name,
                    receiver_phone=order_in.receiver_phone,
                    receiver_address=order_in.receiver_address,
                    notes=order_in.notes,
                    items=order_items_to_create,
                )
                db.add(new_order)

                # 2d. 清空购物车
                await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

            # 提交整个事务
            await db.commit()

        except (InsufficientStockException, InventoryLockException) as e:
            # 如果发生库存不足或锁异常，回滚事务并向上抛出异常
            await db.rollback()
            raise ValueError(str(e))
        finally:
            # 步骤3: 无论成功与否，都要确保所有已获取的锁都被释放
            for lock in locks:
                await lock.release()

        # 步骤4: 返回新创建的、包含完整关联数据的订单
        # 这里需要在事务提交后重新查询，以获取数据库生成的ID和关系
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.sku).selectinload(SKU.attribute_values))
            .where(Order.order_sn == order_sn)
        )
        return result.scalar_one()

    async def create_order_from_selected_cart_items(self, db: AsyncSession, user: User,
                                                    order_in: OrderCreateFromSelected) -> Order:
        """
        从用户购物车中选择指定的商品创建订单
        """
        if not order_in.selected_cart_item_ids:
            raise ValueError("必须选择至少一个购物车商品来创建订单")

        # 1. 获取并验证选中的购物车项 (CartService会预加载sku和sku.product)
        selected_cart_items = await cart_service.get_user_cart_items_by_ids(db, user, order_in.selected_cart_item_ids)

        # 2. 验证找到的商品数量是否与请求的数量一致
        if len(selected_cart_items) != len(set(order_in.selected_cart_item_ids)):
            raise ValueError("选择的购物车商品无效、部分商品不存在或不属于该用户。")

        # 3. 为选中的商品SKU加锁
        sku_ids_to_lock = list(set(item.sku_id for item in selected_cart_items))
        locks = []
        redis = await get_redis_pool()
        new_order = None
        # 预先生成订单号，用于库存预留的关联ID，与全量下单逻辑保持一致
        order_sn = f"SN{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
        try:
            for sku_id in sorted(sku_ids_to_lock):
                lock = RedisLock(redis, f"inventory:sku:{sku_id}", expire_seconds=10)
                if not await lock.acquire():
                    raise InventoryLockException(f"无法获取SKU {sku_id} 的库存锁，请稍后再试。")
                locks.append(lock)

            # 4. 数据库事务
            async with db.begin_nested():
                total_amount = 0.0
                order_items_to_create = []

                for item in selected_cart_items:
                    if not item.sku or not item.sku.product:
                        raise ValueError(f"购物车商品 {item.id} 的SKU或产品信息不完整。")

                    # a. 预留库存，统一使用预先生成的订单号作为关联ID
                    await inventory_service.reserve_stock(
                        db=db,
                        sku_id=item.sku_id,
                        quantity=item.quantity,
                        reference_id=order_sn,
                        reference_type="order_creation",
                        operator_id=user.id,
                        notes=f"为订单 {order_sn} 创建预留库存"
                    )

                    total_amount += item.price * item.quantity
                    order_items_to_create.append(
                        OrderItem(
                            sku_id=item.sku_id,
                            product_name=item.sku.product.name,
                            sku_name=item.sku.name,
                            sku_price=item.price,
                            quantity=item.quantity,
                            sku_image_url=item.sku.image_url
                        )
                    )

                # b. 创建 Order (使用预先生成的order_sn)
                new_order = Order(
                    order_sn=order_sn,
                    user_id=user.id,
                    total_amount=total_amount,
                    pay_amount=total_amount,
                    status=OrderStatusEnum.PENDING_PAYMENT,
                    receiver_name=order_in.receiver_name,
                    receiver_phone=order_in.receiver_phone,
                    receiver_address=order_in.receiver_address,
                    notes=order_in.notes,
                    items=order_items_to_create
                )
                db.add(new_order)

                # c. 从购物车中移除已下单的商品
                await cart_service.remove_items_from_cart(db, user, order_in.selected_cart_item_ids)

            await db.commit()

        except (InsufficientStockException, InventoryLockException) as e:
            await db.rollback()
            raise ValueError(str(e))
        except Exception as e:
            await db.rollback()
            raise Exception(f"创建订单时发生未知内部错误: {e}")
        finally:
            # 6. 释放锁
            for lock in locks:
                await lock.release()

        if not new_order:
            raise Exception("订单创建失败，对象未实例化。")

        # 7. 返回创建的订单 (重新查询以获取完整的关联数据)
        return await self.get_order_by_id(db, new_order.id)

    async def cancel_order(self, db: AsyncSession, order_sn: str, user: Optional[User] = None) -> Order:  # noqa
        """
        取消一个处于“待支付”状态的订单，此方法可由用户或系统调用
        这是一个原子操作，包含在一个数据库事务中
        1. 查找订单并使用悲观锁，防止并发操作
        2. 如果是用户操作，验证订单所有权；如果是系统操作，则跳过
        3. 验证订单状态
        4. 调用库存服务释放为该订单预留的库存
        5. 更新订单状态为“已取消”
        """
        async with db.begin_nested():
            # 步骤 1: 构建基础查询，预先加载所有关联项
            query = (
                select(Order)
                .options(
                    selectinload(Order.items)
                    .selectinload(OrderItem.sku)
                    .selectinload(SKU.attribute_values)
                    .selectinload(AttributeValue.attribute)
                )
                .where(Order.order_sn == order_sn)
            )

            # 步骤 2: 如果是用户发起的取消，则检查订单所有权
            if user:
                query = query.where(Order.user_id == user.id)

            # 添加悲观锁
            query = query.with_for_update()

            result = await db.execute(query)
            order = result.scalar_one_or_none()

            # 步骤 3: 验证订单
            if not order:
                error_message = f'订单号 {order_sn} 对应的订单不存在'
                if user:
                    error_message += '或不属于您'
                raise ValueError(error_message)

            if order.status != OrderStatusEnum.PENDING_PAYMENT:
                raise ValueError(f'订单状态为“{order.status.value}”，无法取消，只有“待支付”的订单才能被取消')

            # 步骤 4: 调用库存服务释放库存
            if user:
                operator_id = user.id
                notes = f"用户取消订单 {order.order_sn}"
            else:
                operator_id = 3  # 3代表系统操作（3为系统管理员）
                notes = f"系统因超时自动取消订单 {order.order_sn}"

            await inventory_service.release_reserved_stock(
                db=db,
                reference_id=order.order_sn,
                original_reference_type="order_creation",
                new_reference_type="order_cancellation",
                operator_id=operator_id,
                notes=notes
            )

            # 步骤 5: 更新订单状态
            order.status = OrderStatusEnum.CANCELLED
            db.add(order)

            return order

    async def get_order_by_id(self, db: AsyncSession, order_id: int, user_id: int = None) -> Order:  # noqa
        query = (
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.sku).selectinload(SKU.attribute_values))
            .where(Order.id == order_id)
        )
        if user_id:
            query = query.where(Order.user_id == user_id)
        result = await db.execute(query)
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"订单 {order_id} 不存在或不属于该用户")
        return order

    async def get_order_by_sn(self, db: AsyncSession, order_sn: str, user_id: int = None) -> Order:  # noqa
        query = (
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.sku).selectinload(SKU.attribute_values))
            .where(Order.order_sn == order_sn)
        )
        if user_id:
            query = query.where(Order.user_id == user_id)
        result = await db.execute(query)
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"订单号 {order_sn} 对应的订单不存在或不属于该用户")
        return order

    async def process_payment_notification(  # noqa
            self,
            db: AsyncSession,
            order_sn: str,
            trade_no: str,
            paid_at: datetime,
            total_amount: float,
    ) -> bool:
        """
        处理支付成功后的异步通知
        这是一个原子操作，包含在一个数据库事务中
        1. 查找订单并加锁，防止并发处理
        2. 验证订单状态，确保幂等性
        3. 更新订单状态为“已支付”，并记录支付信息
        4. 调用库存服务，将预留库存正式提交为出库

        :return: bool, 始终返回True，以告知支付宝无需重试
        """
        try:
            async with db.begin_nested():
                # 步骤 1: 查找订单并使用悲观锁 (SELECT ... FOR UPDATE)
                query = select(Order).where(Order.order_sn == order_sn).with_for_update()
                result = await db.execute(query)
                order = result.scalar_one_or_none()

                if not order:
                    logging.error(f"支付通知处理失败：找不到订单 {order_sn}")
                    return True  # 找不到订单，也告知支付宝成功，避免重试

                # 步骤 2: 幂等性检查
                if order.status != OrderStatusEnum.PENDING_PAYMENT:
                    logging.warning(f"订单 {order_sn} 状态为 {order.status.value}，无需重复处理支付通知。")
                    return True

                # 步骤 3: 验证支付金额
                if order.pay_amount != total_amount:
                    logging.error(
                        f"支付通知处理失败：订单 {order_sn} 金额不匹配。"
                        f"订单金额: {order.pay_amount}, 支付金额: {total_amount}"
                    )
                    return True  # 金额不符，也返回成功，防止重试，记录日志供人工排查

                # 步骤 4: 更新订单状态和支付信息
                order.status = OrderStatusEnum.PROCESSING
                order.pay_time = paid_at
                order.payment_method = "alipay"
                order.trade_no = trade_no
                db.add(order)

                # 步骤 5: 调用库存服务提交预留库存
                await inventory_service.commit_reserved_stock(
                    db=db,
                    order_sn=order.order_sn,
                    operator_id=order.user_id
                )

            await db.commit()
            logging.info(f"订单 {order_sn} 已成功处理支付通知，状态更新为处理中（已支付）。")

        except Exception as e:
            logging.error(f"处理订单 {order_sn} 的支付通知时发生严重错误: {e}", exc_info=True)
            await db.rollback()
            # 即使内部处理失败，也应告知支付宝成功，以防无限重试
            # 失败的订单需要通过日志和监控进行人工介入

        return True


order_service = OrderService()
