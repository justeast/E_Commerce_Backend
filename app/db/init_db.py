import asyncio
import logging

from sqlalchemy import text
from app.db.session import engine
from app.db.base import Base

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


async def init_db() -> None:
    """初始化数据库"""
    await create_tables()
    await update_products_table()  
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(init_db())
