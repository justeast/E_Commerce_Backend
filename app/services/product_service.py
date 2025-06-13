from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_attribute import SKU


class ProductService:
    async def get_sku(self, db: AsyncSession, sku_id: int) -> SKU | None:  # noqa
        """根据ID获取SKU."""
        result = await db.execute(select(SKU).filter(SKU.id == sku_id))
        return result.scalar_one_or_none()


product_service = ProductService()
