# 在此处导入所有现有模型，以便 Alembic 可以检测到它们(作为模型注册中心)
# 用于自动生成迁移.
from app.db.base_class import Base  # noqa

from app.models.user import User  # noqa
from app.models.rbac import Role, Permission, role_permission, user_role  # noqa
from app.models.product import Product, Category, Tag, product_tag  # noqa
from app.models.product_attribute import SKU, Attribute, AttributeValue, sku_attribute_value  # noqa
from app.models.inventory import Warehouse, InventoryItem, InventoryTransaction, InventoryTransactionType  # noqa
from app.models.product_review import ProductReview, ReviewReply  # noqa
from app.models.order import Cart, CartItem, Order, OrderItem, OrderLog  # noqa
from app.models.promotion import Promotion  # noqa
from app.models.coupon import CouponTemplate, UserCoupon  # noqa
from app.models.seckill import SeckillActivity, SeckillProduct  # noqa
