from datetime import datetime
from pydantic import BaseModel

from app.schemas.product_attribute import SKU


class BrowsingHistoryBase(BaseModel):
    sku_id: int
    user_id: int


class BrowsingHistoryCreate(BrowsingHistoryBase):
    pass


class BrowsingHistoryRead(BaseModel):
    id: int
    browsed_at: datetime
    user_id: int
    sku_id: int
    sku: SKU

    class Config:
        from_attributes = True
