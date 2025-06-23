import logging
from typing import List, Optional, Dict
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import (
    Warehouse, InventoryItem, InventoryTransaction,
    InventoryTransactionType
)
from app.models.product_attribute import SKU
from app.core.redis_client import get_redis_pool
from app.utils.messaging import send_alert_to_queue
from app.utils.redis_lock import RedisLock


class InventoryException(Exception):
    """库存异常基类"""
    pass


class InsufficientStockException(InventoryException):
    """库存不足异常"""
    pass


class InventoryLockException(InventoryException):
    """库存锁定异常"""
    pass


class InventoryService:
    """库存服务"""

    @staticmethod
    async def get_sku_stock(
            db: AsyncSession,
            sku_id: int,
            warehouse_id: Optional[int] = None
    ) -> Dict[int, int]:
        """
        获取SKU的库存数量
        :param db:数据库会话
        :param sku_id:sku的id
        :param warehouse_id:仓库的id，如果为None则返回所有仓库的库存
        :return: 仓库ID到库存数量的映射
        """
        query = select(InventoryItem.warehouse_id, InventoryItem.quantity)

        if warehouse_id:
            query = query.where(
                and_(
                    InventoryItem.sku_id == sku_id,
                    InventoryItem.warehouse_id == warehouse_id
                )
            )
        else:
            query = query.where(InventoryItem.sku_id == sku_id)

        result = await db.execute(query)
        return {row[0]: row[1] for row in result.all()}

    @staticmethod
    async def check_stock_availability(
            db: AsyncSession,
            sku_id: int,
            quantity: int,
            warehouse_id: Optional[int] = None
    ) -> bool:
        """
        检查SKU库存是否充足
        :param db:数据库会话
        :param sku_id:sku的id
        :param quantity:需要的数量
        :param warehouse_id:仓库id，如果为None则检查所有仓库的总库存
        :return: bool 库存是否充足
        """
        if warehouse_id:
            # 检查特定仓库的库存
            query = select(func.sum(InventoryItem.quantity - InventoryItem.reserved_quantity)).where(
                and_(
                    InventoryItem.sku_id == sku_id,
                    InventoryItem.warehouse_id == warehouse_id
                )
            )
        else:
            # 检查所有仓库的总库存
            query = select(func.sum(InventoryItem.quantity - InventoryItem.reserved_quantity)).where(
                InventoryItem.sku_id == sku_id
            )

        result = await db.execute(query)
        available_stock = result.scalar() or 0
        return available_stock >= quantity

    @staticmethod
    async def reserve_stock(
            db: AsyncSession,
            sku_id: int,
            quantity: int,
            reference_id: str,
            reference_type: str,
            warehouse_id: Optional[int] = None,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ) -> None:
        """
        预留库存，此方法假定它在一个更大的事务中被调用
        它不处理锁或事务提交/回滚，由调用者负责这些
        :param db:数据库会话
        :param sku_id: sku的id
        :param quantity: 预留数量
        :param reference_id: 关联id（如订单id,当前暂时使用的是自定义格式的id:"reserve_{uuid.uuid4()}"）
        :param reference_type: 关联类型（"reserve"）
        :param warehouse_id: 仓库id，如果为None则自动选择库存充足的仓库
        :param operator_id: 操作员id
        :param notes: 备注
        :return: bool 是否成功预留
        """
        # 1. 检查总可用库存
        is_available = await InventoryService.check_stock_availability(db, sku_id, quantity, warehouse_id)
        if not is_available:
            raise InsufficientStockException(f"SKU {sku_id} 库存不足，需要 {quantity}。")

        # 2. 确定从哪个仓库预留
        items_to_update: List[InventoryItem] = []
        if warehouse_id:
            query = select(InventoryItem).where(
                and_(
                    InventoryItem.sku_id == sku_id,
                    InventoryItem.warehouse_id == warehouse_id
                )
            )
            result = await db.execute(query)
            item = result.scalars().first()
            if item:
                items_to_update.append(item)
        else:
            # 如果未指定仓库，找到第一个有足够可用库存的仓库
            query = select(InventoryItem).where(
                and_(
                    InventoryItem.sku_id == sku_id,
                    (InventoryItem.quantity - InventoryItem.reserved_quantity) >= quantity
                )
            ).order_by(InventoryItem.warehouse_id).limit(1)
            result = await db.execute(query)
            item = result.scalars().first()
            if item:
                items_to_update.append(item)

        if not items_to_update:
            raise InsufficientStockException(f"SKU {sku_id} 在任何单个仓库中都没有足够的库存来满足 {quantity} 的需求。")

        # 3. 更新预留数量并创建事务记录
        for item in items_to_update:
            item.reserved_quantity += quantity
            db.add(item)

            transaction = InventoryTransaction(
                inventory_item_id=item.id,
                transaction_type=InventoryTransactionType.RESERVE,
                quantity=quantity,
                reference_id=reference_id,
                reference_type=reference_type,
                operator_id=operator_id,
                notes=notes
            )
            db.add(transaction)

    @staticmethod
    async def release_reserved_stock(
            db: AsyncSession,
            reference_id: str,
            original_reference_types: List[str],
            new_reference_type: str,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ):
        """
        释放指定关联ID和类型的预留库存
        此方法不处理事务，应由调用方统一管理
        :param db: 数据库会话
        :param reference_id: 关联ID（如订单号或手动预留ID）
        :param original_reference_types: 要查找的原始预留记录的类型列表（如 ['order_creation', 'seckill_order_creation']）
        :param new_reference_type: 新创建的释放流水的类型（如 'order_cancellation' 或 'manual_release'）
        :param operator_id: 操作员ID
        :param notes: 备注
        """
        # 查找所有与该引用和原始类型相关的预留事务
        query = select(InventoryTransaction).where(
            and_(
                InventoryTransaction.reference_id == reference_id,
                InventoryTransaction.reference_type.in_(original_reference_types),
                InventoryTransaction.transaction_type == InventoryTransactionType.RESERVE
            )
        )
        result = await db.execute(query)
        reserve_transactions = result.scalars().all()

        if not reserve_transactions:
            logging.warning(
                f"尝试为(ref_id={reference_id}, ref_types={original_reference_types})释放库存，但未找到任何预留记录。")
            return

        for transaction in reserve_transactions:
            inventory_item = await db.get(InventoryItem, transaction.inventory_item_id)
            if not inventory_item:
                # 在事务中，如果数据不一致，应该抛出异常以触发回滚
                raise ValueError(f"数据不一致：找不到库存项 ID {transaction.inventory_item_id}")

            # 减少预留数量，相当于将库存释放回可用状态
            inventory_item.reserved_quantity -= transaction.quantity
            db.add(inventory_item)

            # 创建一条对应的库存释放流水
            release_transaction = InventoryTransaction(
                inventory_item_id=transaction.inventory_item_id,
                transaction_type=InventoryTransactionType.RELEASE,
                quantity=transaction.quantity,
                reference_id=reference_id,
                reference_type=new_reference_type,
                operator_id=operator_id,
                notes=notes
            )
            db.add(release_transaction)

        logging.info(
            f"已准备为(ref_id={reference_id}, ref_types={original_reference_types})释放 {len(reserve_transactions)} 笔库存。")

    @staticmethod
    async def confirm_stock_out(
            db: AsyncSession,
            reference_id: str,
            reference_type: str,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ) -> bool:
        """
        确认出库（将预留库存转为实际出库）
        :param db: 数据库会话
        :param reference_id: 关联ID（如订单ID）
        :param reference_type: 关联类型（"confirm"）
        :param operator_id: 操作员ID
        :param notes: 备注
        :return: 是否成功出库
        """
        # 查找所有与该引用相关的预留事务
        query = select(InventoryTransaction).where(
            and_(
                InventoryTransaction.reference_id == reference_id,
                InventoryTransaction.reference_type == "reserve",
                InventoryTransaction.transaction_type == InventoryTransactionType.RESERVE
            )
        )
        result = await db.execute(query)
        reserve_transactions = result.scalars().all()

        if not reserve_transactions:
            return False

        try:
            for transaction in reserve_transactions:
                # 获取库存项
                inventory_item_id = transaction.inventory_item_id
                quantity = transaction.quantity

                # 更新库存项，减少总库存和预留数量
                await db.execute(
                    update(InventoryItem)
                    .where(InventoryItem.id == inventory_item_id)
                    .values(
                        quantity=InventoryItem.quantity - quantity,
                        reserved_quantity=InventoryItem.reserved_quantity - quantity
                    )
                )

                # 创建出库事务记录
                stock_out_transaction = InventoryTransaction(
                    inventory_item_id=inventory_item_id,
                    transaction_type=InventoryTransactionType.STOCK_OUT,
                    quantity=quantity,
                    reference_id=reference_id,
                    reference_type=reference_type,
                    operator_id=operator_id,
                    notes=notes
                )
                db.add(stock_out_transaction)

                # 检查是否达到预警阈值
                await InventoryService._check_alert_threshold(db, inventory_item_id)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            raise e

    @staticmethod
    async def stock_in(
            db: AsyncSession,
            sku_id: int,
            warehouse_id: int,
            quantity: int,
            reference_id: Optional[str] = None,
            reference_type: Optional[str] = None,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ) -> bool:
        """
        入库操作
        :param db:数据库会话
        :param sku_id: sku的id
        :param warehouse_id:仓库id
        :param quantity:入库数量
        :param reference_id:关联id（如采购单id）
        :param reference_type:关联类型（如"purchase"）
        :param operator_id:操作员id
        :param notes:备注
        :return:是否成功入库
        """
        try:
            # 获取或创建库存项
            inventory_item = await InventoryService._get_or_create_inventory_item(
                db, sku_id, warehouse_id
            )

            # 更新库存数量
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == inventory_item.id)
                .values(quantity=InventoryItem.quantity + quantity)
            )

            # 创建入库事务记录
            transaction = InventoryTransaction(
                inventory_item_id=inventory_item.id,
                transaction_type=InventoryTransactionType.STOCK_IN,
                quantity=quantity,
                reference_id=reference_id,
                reference_type=reference_type,
                operator_id=operator_id,
                notes=notes
            )
            db.add(transaction)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            raise e

    @staticmethod
    async def adjust_stock(
            db: AsyncSession,
            sku_id: int,
            warehouse_id: int,
            new_quantity: int,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ) -> bool:
        """
        调整库存
        :param db: 数据库会话
        :param sku_id: SKU ID
        :param warehouse_id: 仓库ID
        :param new_quantity: 新的库存数量
        :param operator_id: 操作员ID
        :param notes: 备注
        :return: 是否成功调整
        """
        try:
            # 获取或创建库存项
            inventory_item = await InventoryService._get_or_create_inventory_item(
                db, sku_id, warehouse_id
            )

            # 计算调整数量
            adjustment = new_quantity - inventory_item.quantity

            # 更新库存数量
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == inventory_item.id)
                .values(quantity=new_quantity)
            )

            # 创建库存调整事务记录
            transaction = InventoryTransaction(
                inventory_item_id=inventory_item.id,
                transaction_type=InventoryTransactionType.ADJUST,
                quantity=adjustment,  # 可以是正数或负数
                reference_id=None,
                reference_type="inventory_adjustment",
                operator_id=operator_id,
                notes=notes
            )
            db.add(transaction)

            # 检查是否达到预警阈值
            await InventoryService._check_alert_threshold(db, inventory_item.id)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            raise e

    @staticmethod
    async def transfer_stock(
            db: AsyncSession,
            sku_id: int,
            from_warehouse_id: int,
            to_warehouse_id: int,
            quantity: int,
            operator_id: Optional[int] = None,
            notes: Optional[str] = None
    ) -> bool:
        """
        库存调拨（从一个仓库转移到另一个仓库）
        :param db: 数据库会话
        :param sku_id: SKU ID
        :param from_warehouse_id: 源仓库ID
        :param to_warehouse_id: 目标仓库ID
        :param quantity: 调拨数量
        :param operator_id: 操作员ID
        :param notes: 备注
        :return: 是否成功调拨
        """
        # 获取Redis客户端
        redis = await get_redis_pool()

        # 创建库存锁
        lock = RedisLock(redis, f"inventory:sku:{sku_id}", expire_seconds=5)

        # 尝试获取锁
        if not await lock.acquire():
            raise InventoryLockException(f"无法获取SKU {sku_id} 的库存锁")

        try:
            # 检查源仓库库存是否充足
            if not await InventoryService.check_stock_availability(db, sku_id, quantity, from_warehouse_id):
                raise InsufficientStockException(f"源仓库 {from_warehouse_id} 的 SKU {sku_id} 库存不足")

            # 获取源仓库库存项
            from_item = await InventoryService._get_inventory_item(db, sku_id, from_warehouse_id)

            # 获取或创建目标仓库库存项
            to_item = await InventoryService._get_or_create_inventory_item(db, sku_id, to_warehouse_id)

            # 更新源仓库库存
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == from_item.id)
                .values(quantity=InventoryItem.quantity - quantity)
            )

            # 更新目标仓库库存
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == to_item.id)
                .values(quantity=InventoryItem.quantity + quantity)
            )

            # 创建出库事务记录
            out_transaction = InventoryTransaction(
                inventory_item_id=from_item.id,
                transaction_type=InventoryTransactionType.TRANSFER_OUT,
                quantity=quantity,
                reference_id=f"sku_{sku_id}_to_{to_warehouse_id}",
                reference_type="inventory_transfer",
                operator_id=operator_id,
                notes=notes
            )
            db.add(out_transaction)

            # 创建入库事务记录
            in_transaction = InventoryTransaction(
                inventory_item_id=to_item.id,
                transaction_type=InventoryTransactionType.TRANSFER_IN,
                quantity=quantity,
                reference_id=f"sku_{sku_id}_from_{from_warehouse_id}",
                reference_type="inventory_transfer",
                operator_id=operator_id,
                notes=notes
            )
            db.add(in_transaction)

            # 检查是否达到预警阈值
            await InventoryService._check_alert_threshold(db, from_item.id)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            raise e
        finally:
            # 释放锁
            await lock.release()

    @staticmethod
    async def get_low_stock_items(
            db: AsyncSession,
            warehouse_id: Optional[int] = None
    ) -> List[Dict]:
        """
        获取库存低于预警阈值的商品
        :param db: 数据库会话
        :param warehouse_id: 仓库ID，如果为None则查询所有仓库
        :return: 库存低于预警阈值的商品列表
        """
        # 创建查询，直接在select中指定所有需要的字段
        query = select(
            InventoryItem.id,
            InventoryItem.sku_id,
            InventoryItem.warehouse_id,
            InventoryItem.quantity,
            InventoryItem.reserved_quantity,
            InventoryItem.alert_threshold,
            SKU.code.label("sku_code"),
            SKU.product_id,
            Warehouse.name.label("warehouse_name")
        ).join(
            SKU, InventoryItem.sku_id == SKU.id
        ).join(
            Warehouse, InventoryItem.warehouse_id == Warehouse.id
        ).where(
            InventoryItem.quantity <= InventoryItem.alert_threshold
        )

        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)

        result = await db.execute(query)

        # 将结果转换为字典列表
        items = []
        for row in result:
            item = {
                'id': row.id,
                'sku_id': row.sku_id,
                'sku_code': row.sku_code,
                'product_id': row.product_id,
                'warehouse_id': row.warehouse_id,
                'warehouse_name': row.warehouse_name,
                'quantity': row.quantity,
                'reserved_quantity': row.reserved_quantity,
                'available_quantity': row.quantity - row.reserved_quantity,
                'alert_threshold': row.alert_threshold
            }
            items.append(item)

        return items

    # 辅助方法
    @staticmethod
    async def _get_inventory_item(
            db: AsyncSession,
            sku_id: int,
            warehouse_id: int
    ) -> InventoryItem:
        """获取库存项"""
        query = select(InventoryItem).where(
            and_(
                InventoryItem.sku_id == sku_id,
                InventoryItem.warehouse_id == warehouse_id
            )
        )
        result = await db.execute(query)
        item = result.scalars().first()

        if not item:
            raise ValueError(f"找不到SKU {sku_id} 在仓库 {warehouse_id} 的库存记录")

        return item

    @staticmethod
    async def _get_or_create_inventory_item(
            db: AsyncSession,
            sku_id: int,
            warehouse_id: int
    ) -> InventoryItem:
        """获取或创建库存项"""
        try:
            return await InventoryService._get_inventory_item(db, sku_id, warehouse_id)
        except ValueError:
            # 检查SKU和仓库是否存在
            sku_result = await db.execute(select(SKU).where(SKU.id == sku_id))
            sku = sku_result.scalars().first()
            if not sku:
                raise ValueError(f"找不到SKU {sku_id}")

            warehouse_result = await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
            warehouse = warehouse_result.scalars().first()
            if not warehouse:
                raise ValueError(f"找不到仓库 {warehouse_id}")

            # 创建新的库存项
            item = InventoryItem(
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                quantity=0,
                reserved_quantity=0
            )
            db.add(item)
            await db.flush()
            return item

    @staticmethod
    async def _select_warehouses_for_stock(
            db: AsyncSession,
            sku_id: int,
            quantity: int
    ) -> List[InventoryItem]:
        """选择合适的仓库进行出库"""
        query = select(InventoryItem).where(
            and_(
                InventoryItem.sku_id == sku_id,
                InventoryItem.quantity - InventoryItem.reserved_quantity >= quantity
            )
        ).order_by(InventoryItem.quantity.desc())

        result = await db.execute(query)
        items = result.scalars().all()

        if not items:
            raise InsufficientStockException(f"所有仓库的SKU {sku_id} 库存都不足")

        # 简单策略：选择库存最多的仓库
        return [items[0]]

    @staticmethod
    async def _check_alert_threshold(
            db: AsyncSession,
            inventory_item_id: int
    ) -> bool:
        """检查是否达到预警阈值"""
        query = select(InventoryItem).where(InventoryItem.id == inventory_item_id)
        result = await db.execute(query)
        item = result.scalars().first()

        if item and item.quantity <= item.alert_threshold:
            # 准备基本预警数据
            alert_data = {
                'inventory_item_id': inventory_item_id,
                'quantity': item.quantity,
                'alert_threshold': item.alert_threshold,
                'available_quantity': item.quantity - item.reserved_quantity
            }

            # 发送预警到队列
            await send_alert_to_queue(alert_data)
            return True

        return False

    async def commit_reserved_stock(
            self,
            db: AsyncSession,
            order_sn: str,
            operator_id: Optional[int] = None
    ) -> None:
        """
        提交预留库存（支付成功后调用），将预留库存转为实际出库
        此方法不管理自己的事务，由调用方（如OrderService）负责
        :param db: 数据库会话
        :param order_sn: 订单号，作为预留时的关联ID
        :param operator_id: 操作员ID
        """
        # 1. 查找此订单创建时产生的所有预留事务
        query = select(InventoryTransaction).where(
            and_(
                InventoryTransaction.reference_id == order_sn,
                InventoryTransaction.reference_type == "order_creation",
                InventoryTransaction.transaction_type == InventoryTransactionType.RESERVE
            )
        )
        result = await db.execute(query)
        reserve_transactions = result.scalars().all()

        if not reserve_transactions:
            logging.warning(f"未找到订单 {order_sn} 的库存预留记录，可能已被处理。")
            return

        # 2. 对每一笔预留，进行库存提交操作
        for tx in reserve_transactions:
            # a. 更新库存项：总库存和预留库存都扣减
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == tx.inventory_item_id)
                .values(
                    quantity=InventoryItem.quantity - tx.quantity,
                    reserved_quantity=InventoryItem.reserved_quantity - tx.quantity
                )
            )

            # b. 创建一条新的“出库”事务记录
            stock_out_tx = InventoryTransaction(
                inventory_item_id=tx.inventory_item_id,
                transaction_type=InventoryTransactionType.STOCK_OUT,
                quantity=tx.quantity,
                reference_id=order_sn,
                reference_type="payment_confirmation",
                operator_id=operator_id,
                notes=f"订单 {order_sn} 支付成功，确认出库。"
            )
            db.add(stock_out_tx)

            # c. 检查库存预警
            await self._check_alert_threshold(db, tx.inventory_item_id)


inventory_service = InventoryService()
