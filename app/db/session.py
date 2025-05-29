from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# 创建异步数据库引擎
db_url = settings.DATABASE_URL
engine = create_async_engine(db_url, echo=True, future=True)

# 创建异步会话工厂
async_session = sessionmaker(  # type: ignore
    engine, class_=AsyncSession, expire_on_commit=False
)


# 获取数据库会话的依赖函数
async def get_db() -> AsyncSession:
    """获取数据库会话的依赖函数"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# 关闭数据库引擎
async def close_db_connection():
    """关闭数据库连接"""
    await engine.dispose()
