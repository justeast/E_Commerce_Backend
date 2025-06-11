"""api路由配置"""

from fastapi import APIRouter
from app.api.v1.endpoints import users, auth, rbac, categories, tags, products, attributes, attribute_values, skus, \
    product_reviews, product_search, warehouses, inventory

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

# 添加商品属性路由
api_router.include_router(attributes.router, prefix="/attributes", tags=["attributes"])

# 添加属性值路由
api_router.include_router(attribute_values.router, prefix="/attribute-values", tags=["attribute_values"])

# 添加SKU路由
api_router.include_router(skus.router, prefix="/skus", tags=["skus"])

# 添加商品评价路由
api_router.include_router(product_reviews.router, prefix="/product-reviews", tags=["product_reviews"])

# 添加商品搜索路由
api_router.include_router(product_search.router, prefix="/product-search", tags=["product_search"])

# 添加仓库管理路由
api_router.include_router(warehouses.router, prefix="/warehouses", tags=["warehouses"])

# 添加库存管理路由
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
