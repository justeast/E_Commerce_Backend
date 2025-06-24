"""api路由配置"""

from fastapi import APIRouter
from app.api.v1.endpoints import users, auth, rbac, categories, tags, products, attributes, attribute_values, skus, \
    product_reviews, product_search, warehouses, inventory, cart, orders, payment, promotions, coupon, seckill, \
    user_behavior, recommendations, user_profile

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

# 添加购物车路由
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])

# 添加订单路由
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])

# 注册支付路由
api_router.include_router(payment.router, tags=["Payment"])

# 添加促销活动路由
api_router.include_router(promotions.router, prefix="/promotions", tags=["Promotions"])

# 添加优惠券路由
api_router.include_router(coupon.router, prefix="/coupons", tags=["Coupons"])

# 添加秒杀活动路由
api_router.include_router(seckill.router, prefix="/seckill", tags=["seckill"])

# 添加用户行为路由
api_router.include_router(user_behavior.router, prefix="/user", tags=["User Behavior"])

# 推荐系统路由
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

# 用户画像路由
api_router.include_router(user_profile.router, prefix="/user/profile", tags=["User Profile"])
