import asyncio
import logging

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


async def init_db() -> None:
    """初始化数据库"""
    await create_tables()
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(init_db())
