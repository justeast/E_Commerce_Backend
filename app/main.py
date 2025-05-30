from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.v1.api import api_router
from app.db.init_db import init_db
from app.db.session import close_db_connection
from app.utils.init_rbac import init_rbac


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期事件处理器"""
    # 启动时执行
    import os

    # 直接设置环境变量为true，强制执行初始化(初始化一次就好)
    # os.environ["INIT_DB_AND_RBAC"] = "true"

    # 检查是否需要初始化数据库和RBAC
    init_required = os.environ.get("INIT_DB_AND_RBAC", "false").lower() == "true"

    if init_required:
        # 初始化数据库
        await init_db()
        # 初始化RBAC系统
        await init_rbac()
        logging.info("数据库和RBAC系统初始化完成")
    else:
        logging.info("跳过数据库和RBAC系统初始化")

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
