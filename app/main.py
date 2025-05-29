from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.db.init_db import init_db
from app.db.session import close_db_connection


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期事件处理器"""
    # 启动时执行
    await init_db()
    yield
    # 关闭时执行
    await close_db_connection()


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
