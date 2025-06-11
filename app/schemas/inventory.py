from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from enum import Enum


# 库存交易事务类型枚举
class InventoryTransactionTypeEnum(str, Enum):
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    RESERVE = "reserve"
    RELEASE = "release"
    ADJUST = "adjust"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


# 仓库基础模型
class WarehouseBase(BaseModel):
    name: str
    location: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = Field(None, pattern=r"^\+?[0-9]{8,15}$")
    contact_email: Optional[str] = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    is_active: bool = True
    description: Optional[str] = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class WarehouseInDB(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Warehouse(WarehouseInDB):
    pass


# 库存项基础模型
class InventoryItemBase(BaseModel):
    sku_id: int
    warehouse_id: int
    quantity: int = 0
    reserved_quantity: int = 0
    alert_threshold: Optional[int] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    quantity: Optional[int] = None
    reserved_quantity: Optional[int] = None
    alert_threshold: Optional[int] = None


class InventoryItemInDB(InventoryItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventoryItem(InventoryItemInDB):
    available_quantity: int

    @field_validator("available_quantity", mode="before")
    def calculate_available_quantity(cls, v, info: ValidationInfo):
        data = info.data  # 这才是实际的数据字典
        return data.get("quantity", 0) - data.get("reserved_quantity", 0)


# 库存交易基础模型
class InventoryTransactionBase(BaseModel):
    inventory_item_id: int
    quantity: int
    transaction_type: InventoryTransactionTypeEnum
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    notes: Optional[str] = None


class InventoryTransactionCreate(InventoryTransactionBase):
    pass


class InventoryTransactionInDB(InventoryTransactionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class InventoryTransaction(InventoryTransactionInDB):
    pass


# 库存操作相关模型
class StockInRequest(BaseModel):
    sku_id: int
    warehouse_id: int
    quantity: int = Field(..., gt=0)
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    notes: Optional[str] = None


class StockReserveRequest(BaseModel):
    sku_id: int
    warehouse_id: int
    quantity: int = Field(..., gt=0)
    reference_type: str = "reserve"
    notes: Optional[str] = None


class StockReleaseRequest(BaseModel):
    reference_id: str
    reference_type: str = "release"
    notes: Optional[str] = None


class StockConfirmRequest(BaseModel):
    reference_id: str
    reference_type: str = "confirm"
    notes: Optional[str] = None


class StockAdjustRequest(BaseModel):
    sku_id: int
    warehouse_id: int
    new_quantity: int = Field(..., ge=0)
    reason: str
    notes: Optional[str] = None


class BulkStockAdjustRequest(BaseModel):
    adjustments: List[StockAdjustRequest]


class StockTransferRequest(BaseModel):
    sku_id: int
    source_warehouse_id: int
    target_warehouse_id: int
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None


class BulkStockTransferRequest(BaseModel):
    transfers: List[StockTransferRequest]


# 库存操作响应相关模型
class InventoryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class InventoryItemWithSKU(InventoryItem):
    sku_code: Optional[str] = None
    sku_price: Optional[float] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None

    class Config:
        from_attributes = True


class LowStockAlert(BaseModel):
    inventory_item_id: int
    sku_id: int
    sku_code: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    warehouse_id: int
    warehouse_name: str
    current_quantity: int
    reserved_quantity: int
    available_quantity: int
    alert_threshold: int


class LowStockAlertResponse(BaseModel):
    items: List[LowStockAlert]
    total: int


class InventoryItemResponse(BaseModel):
    success: bool
    message: str
    data: Optional[InventoryItemWithSKU] = None


class InventoryItemsResponse(BaseModel):
    success: bool
    message: str
    data: List[InventoryItemWithSKU]
    total: int
    page: int
    size: int


class WarehouseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Warehouse] = None


class WarehousesResponse(BaseModel):
    success: bool
    message: str
    data: List[Warehouse]
    total: int
    page: int
    size: int


class InventoryTransactionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[InventoryTransaction] = None


class InventoryTransactionsResponse(BaseModel):
    success: bool
    message: str
    data: List[InventoryTransaction]
    total: int
    page: int
    size: int
