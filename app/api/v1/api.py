"""api路由配置"""

from fastapi import APIRouter
from app.api.v1.endpoints import users, auth, rbac, categories, tags, products

api_router = APIRouter()

# 注册用户相关路由
api_router.include_router(users.router, prefix="/users", tags=["users"])

# 添加认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 添加RBAC路由
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])

# 添加商品分类路由
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])

# 添加商品标签路由
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])

# 添加商品路由
api_router.include_router(products.router, prefix="/products", tags=["products"])
