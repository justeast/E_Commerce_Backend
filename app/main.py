from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.v1.api import api_router
from app.db.session import close_db_connection
from app.utils.elasticsearch_connect import close_elasticsearch_connection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    应用生命周期管理器
    """
    logger.info("应用启动...")
    yield
    logger.info("应用关闭...")
    await close_db_connection()
    await close_elasticsearch_connection()
    logger.info("数据库和Elasticsearch连接已关闭")


app = FastAPI(
    title="Ecommerce API",
    description="基于FastAPI的Ecommerce API",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 根路由
@app.get("/")
async def root():
    return {"message": "Welcome to the Ecommerce API!"}


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 注册API路由
app.include_router(api_router, prefix="/api/v1")
