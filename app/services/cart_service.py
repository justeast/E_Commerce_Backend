from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Cart, CartItem
from app.models.product_attribute import SKU
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemUpdate
from app.services.product_service import product_service


class CartService:
    async def get_user_cart(self, db: AsyncSession, user: User) -> Cart:  # noqa
        """获取用户的购物车，如果不存在则创建一个"""
        result = await db.execute(
            select(Cart)
            .filter(Cart.user_id == user.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.sku)
                .selectinload(SKU.attribute_values)
            )
        )
        cart = result.scalar_one_or_none()

        if not cart:
            cart = Cart(user_id=user.id)
            db.add(cart)
            # 对于一个尚未提交到数据库的临时（pending）对象，
            # 我们可以安全地初始化其关系集合为空列表，这不会触发数据库IO。
            cart.items = []

        return cart

    async def add_item_to_cart(self, db: AsyncSession, user: User, item_in: CartItemCreate) -> Cart:
        """将商品添加到用户的购物车"""
        sku = await product_service.get_sku(db, item_in.sku_id)
        if not sku or not sku.is_active:
            raise ValueError("SKU不存在或未激活")

        cart = await self.get_user_cart(db, user)

        # 检查商品是否已在购物车中
        cart_item = next((item for item in cart.items if item.sku_id == item_in.sku_id), None)

        if cart_item:
            # 商品已存在，检查总数量是否超过库存
            new_quantity = cart_item.quantity + item_in.quantity
            if sku.stock < new_quantity:
                raise ValueError("库存不足")
            cart_item.quantity = new_quantity
        else:
            # 商品不存在，检查新增数量是否超过库存
            if sku.stock < item_in.quantity:
                raise ValueError("库存不足")
            # 创建新的购物车项目
            # 关键修复：不直接使用 cart.id，因为它对于新创建的cart对象是None。
            # 而是通过关系属性 cart=cart 来建立连接。
            # SQLAlchemy会在commit时自动处理外键的赋值。
            cart_item = CartItem(
                cart=cart,
                sku_id=item_in.sku_id,
                quantity=item_in.quantity,
                price=sku.price  # 记录添加时的价格
            )
            db.add(cart_item)

        await db.commit()
        db.expunge(cart)  # 从会话缓存中移除旧的cart对象
        return await self.get_user_cart(db, user)  # 返回最新状态的购物车以包含新增的商品

    async def update_cart_item_quantity(self, db: AsyncSession, user: User, cart_item_id: int,
                                        item_in: CartItemUpdate) -> Cart | None:
        """更新用户购物车中商品的数量"""
        cart = await self.get_user_cart(db, user)
        cart_item = next((item for item in cart.items if item.id == cart_item_id), None)

        if not cart_item:
            return None  # 或抛出异常

        if cart_item.sku.stock < item_in.quantity:
            raise ValueError("库存不足")

        cart_item.quantity = item_in.quantity
        await db.commit()
        db.expunge(cart)  # 从会话缓存中移除旧的cart对象
        # 重新从数据库获取最新状态
        return await self.get_user_cart(db, user)

    async def remove_cart_item(self, db: AsyncSession, user: User, cart_item_id: int) -> Cart | None:
        """从用户的购物车中移除商品"""
        cart = await self.get_user_cart(db, user)
        cart_item = next((item for item in cart.items if item.id == cart_item_id), None)

        if not cart_item:
            return None  # 或抛出异常

        await db.delete(cart_item)
        await db.commit()
        db.expunge(cart)  # 从会话缓存中移除旧的cart对象
        # 重新从数据库获取最新状态
        return await self.get_user_cart(db, user)

    async def clear_cart(self, db: AsyncSession, user: User) -> Cart:
        """清空用户的购物车"""
        cart = await self.get_user_cart(db, user)
        if not cart.items:
            return cart  # 购物车已空，无需操作，直接返回

        # 高效地一次性删除所有购物车项目
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()
        db.expunge(cart)  # 从会话缓存中移除旧的cart对象
        return await self.get_user_cart(db, user)  # 返回空的购物车

    async def get_user_cart_items_by_ids(self, db: AsyncSession, user: User, cart_item_ids: List[int]) -> List[
        CartItem]:
        """获取用户购物车中指定ID列表的商品项，并预加载SKU和产品信息"""
        if not cart_item_ids:
            return []

        cart = await self.get_user_cart(db, user)  # 确保购物车存在且属于该用户
        if not cart:
            return []

        result = await db.execute(
            select(CartItem)
            .where(
                CartItem.cart_id == cart.id,  # 确保商品项属于用户的购物车
                CartItem.id.in_(cart_item_ids)
            )
            .options(
                selectinload(CartItem.sku)
                .selectinload(SKU.product)  # 预加载产品信息以获取产品名
            )
        )
        return list(result.scalars().all())

    async def remove_items_from_cart(self, db: AsyncSession, user: User, cart_item_ids: List[int]):
        """从用户的购物车中移除指定ID列表的商品项(在事务中调用，不单独commit)"""
        if not cart_item_ids:
            return

        cart = await self.get_user_cart(db, user)
        if not cart or not cart.items:
            return

        # 执行删除，由外部的OrderService事务来commit
        await db.execute(
            delete(CartItem)
            .where(
                CartItem.cart_id == cart.id,
                CartItem.id.in_(cart_item_ids)
            )
        )


cart_service = CartService()
