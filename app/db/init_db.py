import asyncio
import logging

from sqlalchemy import text
from app.db.session import engine
from app.db.base_class import Base

# 导入所有模型，确保它们被注册到Base.metadata中
from app.models.user import User  # noqa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """创建所有表"""
    logger.info("创建数据库表...")

    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)

    logger.info("数据库表创建完成")


async def update_products_table() -> None:
    """更新products表，添加price和stock字段"""
    logger.info("检查并更新products表结构...")

    async with engine.begin() as conn:
        # 检查price列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'products' AND column_name = 'price'"
        ))
        has_price = result.scalar() > 0

        # 检查stock列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'products' AND column_name = 'stock'"
        ))
        has_stock = result.scalar() > 0

        # 添加缺失的列
        if not has_price:
            logger.info("添加price列到products表")
            await conn.execute(text("ALTER TABLE products ADD COLUMN price FLOAT NOT NULL DEFAULT 0"))

        if not has_stock:
            logger.info("添加stock列到products表")
            await conn.execute(text("ALTER TABLE products ADD COLUMN stock INT NOT NULL DEFAULT 0"))

    logger.info("products表结构更新完成")


async def update_warehouses_table() -> None:
    """更新warehouses表，添加contact_name, contact_phone, contact_email和description字段"""
    logger.info("检查并更新warehouses表结构...")

    async with engine.begin() as conn:
        # 检查contact_info列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'warehouses' AND column_name = 'contact_info'"
        ))
        has_contact_info = result.scalar() > 0

        # 如果存在contact_info列，先删除
        if has_contact_info:
            logger.info("删除旧的contact_info列")
            await conn.execute(text("ALTER TABLE warehouses DROP COLUMN contact_info"))

        # 检查contact_name列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'warehouses' AND column_name = 'contact_name'"
        ))
        has_contact_name = result.scalar() > 0

        # 检查contact_phone列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'warehouses' AND column_name = 'contact_phone'"
        ))
        has_contact_phone = result.scalar() > 0

        # 检查contact_email列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'warehouses' AND column_name = 'contact_email'"
        ))
        has_contact_email = result.scalar() > 0

        # 检查description列是否存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'warehouses' AND column_name = 'description'"
        ))
        has_description = result.scalar() > 0

        # 添加缺失的列
        if not has_contact_name:
            logger.info("添加contact_name列到warehouses表")
            await conn.execute(text("ALTER TABLE warehouses ADD COLUMN contact_name VARCHAR(50)"))

        if not has_contact_phone:
            logger.info("添加contact_phone列到warehouses表")
            await conn.execute(text("ALTER TABLE warehouses ADD COLUMN contact_phone VARCHAR(20)"))

        if not has_contact_email:
            logger.info("添加contact_email列到warehouses表")
            await conn.execute(text("ALTER TABLE warehouses ADD COLUMN contact_email VARCHAR(100)"))

        if not has_description:
            logger.info("添加description列到warehouses表")
            await conn.execute(text("ALTER TABLE warehouses ADD COLUMN description TEXT"))

    logger.info("warehouses表结构更新完成")


async def init_db() -> None:
    """初始化数据库"""
    await create_tables()
    await update_products_table()
    await update_warehouses_table()
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(init_db())
