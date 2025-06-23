from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

from app.core.config import settings

# 创建异步数据库引擎
db_url = settings.DATABASE_URL

# 对于 Celery worker，使用 NullPool 来避免线程的事件循环问题
# 对于主 FastAPI 应用程序，使用默认连接池来提高性能
if os.environ.get("RUNNING_IN_CELERY") == "true":
    engine = create_async_engine(db_url, echo=True, poolclass=NullPool)
else:
    engine = create_async_engine(db_url, echo=True)

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
