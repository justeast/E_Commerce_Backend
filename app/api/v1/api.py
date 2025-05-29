"""api路由配置"""

from fastapi import APIRouter
from app.api.v1.endpoints import users, auth

api_router = APIRouter()

# 注册用户相关路由
api_router.include_router(users.router, prefix="/users", tags=["users"])

# 添加认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
