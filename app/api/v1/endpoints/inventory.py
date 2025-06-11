import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, desc

from app.api.deps import get_db, has_permission, get_current_user
from app.models.user import User
from app.models.inventory import Warehouse, InventoryItem, InventoryTransaction
from app.models.product_attribute import SKU
from app.models.product import Product
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemsResponse,
    InventoryTransactionsResponse,
    StockInRequest,
    StockReserveRequest,
    StockReleaseRequest,
    StockConfirmRequest,
    StockAdjustRequest,
    StockTransferRequest,
    InventoryResponse,
    LowStockAlert,
    LowStockAlertResponse,
    InventoryItemWithSKU,
    BulkStockAdjustRequest,
    BulkStockTransferRequest
)
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_in: InventoryItemCreate,
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    创建库存项
    """
    # 检查SKU是否存在
    sku_query = select(SKU).where(SKU.id == item_in.sku_id)
    sku_result = await db.execute(sku_query)
    sku = sku_result.scalars().first()

    if not sku:
        return InventoryItemResponse(
            success=False,
            message=f"SKU with ID {item_in.sku_id} not found",
            data=None
        )

    # 检查仓库是否存在
    warehouse_query = select(Warehouse).where(
        Warehouse.id == item_in.warehouse_id,
        Warehouse.is_active == True
    )
    warehouse_result = await db.execute(warehouse_query)
    warehouse = warehouse_result.scalars().first()

    if not warehouse:
        return InventoryItemResponse(
            success=False,
            message=f"Active warehouse with ID {item_in.warehouse_id} not found",
            data=None
        )

    # 检查此 SKU 和仓库的库存商品是否已经存在
    item_query = select(InventoryItem).where(
        InventoryItem.sku_id == item_in.sku_id,
        InventoryItem.warehouse_id == item_in.warehouse_id
    )
    item_result = await db.execute(item_query)
    existing_item = item_result.scalars().first()

    if existing_item:
        return InventoryItemResponse(
            success=False,
            message=f"Inventory item already exists for SKU {item_in.sku_id} in warehouse {item_in.warehouse_id}",
            data=None
        )

    # 创建新的库存项
    db_item = InventoryItem(**item_in.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)

    # 获取响应的相关数据
    result = await db.execute(
        select(InventoryItem, SKU, Product)
        .join(SKU, InventoryItem.sku_id == SKU.id)
        .join(Product, SKU.product_id == Product.id)
        .where(InventoryItem.id == db_item.id)
    )
    item_data = result.first()

    if not item_data:
        # 使用InventoryItemWithSKU模型创建正确类型的对象
        # 使用model_validate方法进行转换
        response_data = InventoryItemWithSKU.model_validate(db_item)

        return InventoryItemResponse(
            success=True,
            message="Inventory item created successfully",
            data=response_data
        )

    item, sku, product = item_data
    # 使用model_validate方法创建InventoryItemWithSKU对象
    response_data = InventoryItemWithSKU.model_validate({
        **item.__dict__,
        "sku_code": sku.code,
        "sku_price": sku.price,
        "product_id": product.id,
        "product_name": product.name,
        "available_quantity": item.quantity - item.reserved_quantity
    })

    return InventoryItemResponse(
        success=True,
        message="Inventory item created successfully",
        data=response_data
    )


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_id: int = Path(..., gt=0),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    按 ID 获取单个库存项
    """
    result = await db.execute(
        select(InventoryItem, SKU, Product, Warehouse)
        .join(SKU, InventoryItem.sku_id == SKU.id)
        .join(Product, SKU.product_id == Product.id)
        .join(Warehouse, InventoryItem.warehouse_id == Warehouse.id)
        .where(InventoryItem.id == item_id)
    )
    item_data = result.first()

    if not item_data:
        return InventoryItemResponse(
            success=False,
            message=f"Inventory item with ID {item_id} not found",
            data=None
        )

    item, sku, product, warehouse = item_data
    # 使用model_validate方法创建InventoryItemWithSKU对象
    response_data = InventoryItemWithSKU.model_validate({
        **item.__dict__,
        "sku_code": sku.code,
        "sku_price": sku.price,
        "product_id": product.id,
        "product_name": product.name,
        "available_quantity": item.quantity - item.reserved_quantity
    })

    return InventoryItemResponse(
        success=True,
        message="Inventory item retrieved successfully",
        data=response_data
    )


@router.get("/items", response_model=InventoryItemsResponse)
async def list_inventory_items(
        *,
        db: AsyncSession = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        warehouse_id: Optional[int] = Query(None),
        sku_id: Optional[int] = Query(None),
        product_id: Optional[int] = Query(None),
        low_stock: Optional[bool] = Query(None),
        _: User = Depends(has_permission("inventory:read"))
):
    """
    列出库存项，可选择按仓库、SKU、商品等进行筛选
    """
    # 包含相关数据的库存项的基本查询
    query = (
        select(InventoryItem, SKU, Product, Warehouse)
        .join(SKU, InventoryItem.sku_id == SKU.id)
        .join(Product, SKU.product_id == Product.id)
        .join(Warehouse, InventoryItem.warehouse_id == Warehouse.id)
    )

    # Count query for total
    count_query = select(func.count()).select_from(InventoryItem)

    # 应用筛选
    filters = []
    if warehouse_id is not None:
        filters.append(InventoryItem.warehouse_id == warehouse_id)

    if sku_id is not None:
        filters.append(InventoryItem.sku_id == sku_id)

    if product_id is not None:
        filters.append(SKU.product_id == product_id)
        count_query = (
            select(func.count())
            .select_from(InventoryItem)
            .join(SKU, InventoryItem.sku_id == SKU.id)
            .where(SKU.product_id == product_id)
        )

    if low_stock is not None and low_stock:
        filters.append(
            and_(
                InventoryItem.alert_threshold.isnot(None),
                InventoryItem.quantity <= InventoryItem.alert_threshold
            )
        )

    if filters:
        query = query.where(and_(*filters))
        if not product_id:
            count_query = count_query.where(and_(*filters))

    # total count
    result = await db.execute(count_query)
    total = result.scalar()

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    items_data = result.all()

    # 使用model_validate方法创建InventoryItemWithSKU对象列表
    formatted_items = [
        InventoryItemWithSKU.model_validate({
            **item.__dict__,
            "sku_code": sku.code,
            "sku_price": sku.price,
            "product_id": product.id,
            "product_name": product.name,
            "available_quantity": item.quantity - item.reserved_quantity
        })
        for item, sku, product, warehouse in items_data
    ]

    return InventoryItemsResponse(
        success=True,
        message="Inventory items retrieved successfully",
        data=formatted_items,
        total=total,
        page=skip // limit + 1,
        size=limit
    )


@router.put("/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_id: int = Path(..., gt=0),
        item_in: InventoryItemUpdate,
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    更新库存项
    """
    query = select(InventoryItem).where(InventoryItem.id == item_id)
    result = await db.execute(query)
    item = result.scalars().first()

    if not item:
        return InventoryItemResponse(
            success=False,
            message=f"Inventory item with ID {item_id} not found",
            data=None
        )

    # 更新库存项
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    result = await db.execute(
        select(InventoryItem, SKU, Product)
        .join(SKU, InventoryItem.sku_id == SKU.id)
        .join(Product, SKU.product_id == Product.id)
        .where(InventoryItem.id == item_id)
    )
    item_data = result.first()

    item, sku, product = item_data
    response_data = InventoryItemWithSKU.model_validate({
        **item.__dict__,
        "sku_code": sku.code,
        "sku_price": sku.price,
        "product_id": product.id,
        "product_name": product.name,
        "available_quantity": item.quantity - item.reserved_quantity
    })

    return InventoryItemResponse(
        success=True,
        message="Inventory item updated successfully",
        data=response_data
    )


@router.delete("/items/{item_id}", response_model=InventoryResponse)
async def delete_inventory_item(
        *,
        db: AsyncSession = Depends(get_db),
        item_id: int = Path(..., gt=0),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    删除库存项
    """
    query = select(InventoryItem).where(InventoryItem.id == item_id)
    result = await db.execute(query)
    item = result.scalars().first()

    if not item:
        return InventoryResponse(
            success=False,
            message=f"Inventory item with ID {item_id} not found",
            data=None
        )

    await db.delete(item)
    await db.commit()

    return InventoryResponse(
        success=True,
        message="Inventory item deleted successfully",
        data=None
    )


@router.get("/transactions", response_model=InventoryTransactionsResponse)
async def list_inventory_transactions(
        *,
        db: AsyncSession = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        inventory_item_id: Optional[int] = Query(None),
        transaction_type: Optional[str] = Query(None),
        reference_id: Optional[str] = Query(None),
        reference_type: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        _: User = Depends(has_permission("inventory:read"))
):
    """
    获取库存交易记录
    """
    query = select(InventoryTransaction)
    count_query = select(func.count()).select_from(InventoryTransaction)

    # 过滤
    filters = []
    if inventory_item_id is not None:
        filters.append(InventoryTransaction.inventory_item_id == inventory_item_id)

    if transaction_type is not None:
        filters.append(InventoryTransaction.transaction_type == transaction_type)

    if reference_id is not None:
        filters.append(InventoryTransaction.reference_id == reference_id)

    if reference_type is not None:
        filters.append(InventoryTransaction.reference_type == reference_type)

    if start_date is not None:
        filters.append(InventoryTransaction.created_at >= start_date)

    if end_date is not None:
        filters.append(InventoryTransaction.created_at <= end_date)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # 排序
    query = query.order_by(desc(InventoryTransaction.created_at))

    # total count
    result = await db.execute(count_query)
    total = result.scalar()

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return InventoryTransactionsResponse(
        success=True,
        message="Inventory transactions retrieved successfully",
        data=list(transactions),
        total=total,
        page=skip // limit + 1,
        size=limit
    )


@router.post("/stock/in", response_model=InventoryResponse)
async def stock_in(
        *,
        db: AsyncSession = Depends(get_db),
        stock_in_data: StockInRequest,
        current_user: User = Depends(get_current_user),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    入库
    """
    inventory_service = InventoryService()

    try:
        await inventory_service.stock_in(
            db=db,
            sku_id=stock_in_data.sku_id,
            warehouse_id=stock_in_data.warehouse_id,
            quantity=stock_in_data.quantity,
            reference_id=stock_in_data.reference_id,
            reference_type=stock_in_data.reference_type,
            notes=stock_in_data.notes,
            operator_id=current_user.id
        )

        return InventoryResponse(
            success=True,
            message=f"Successfully added {stock_in_data.quantity} units to inventory",
            data=None
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/reserve", response_model=InventoryResponse)
async def reserve_stock(
        *,
        db: AsyncSession = Depends(get_db),
        reserve_data: StockReserveRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    库存预留(下单)，主要是为了配合stock/confirm(支付完成出库)和stock/release(订单取消)使用，也用于：
    预售、预定等只需要预留库存而不立即出库的场景
    """
    inventory_service = InventoryService()

    # 生成唯一的reference_id
    reference_id = f"reserve_{uuid.uuid4()}"

    try:
        await inventory_service.reserve_stock(
            db=db,
            sku_id=reserve_data.sku_id,
            warehouse_id=reserve_data.warehouse_id,
            quantity=reserve_data.quantity,
            reference_id=reference_id,
            reference_type=reserve_data.reference_type,
            notes=reserve_data.notes,
            operator_id=current_user.id
        )

        return InventoryResponse(
            success=True,
            message=f"Successfully reserved {reserve_data.quantity} units",
            data={"reference_id": reference_id}
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/release", response_model=InventoryResponse)
async def release_stock(
        *,
        db: AsyncSession = Depends(get_db),
        release_data: StockReleaseRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    释放预留库存，主要是为了配合stock/reserve使用，如：
    先预留后取消的场景(订单超时未支付、用户取消订单等)
    """
    inventory_service = InventoryService()

    try:
        await inventory_service.release_reserved_stock(
            db=db,
            reference_id=release_data.reference_id,
            reference_type=release_data.reference_type,
            notes=release_data.notes,
            operator_id=current_user.id
        )

        return InventoryResponse(
            success=True,
            message=f"Successfully released reserved stock for reference {release_data.reference_id}",
            data=None
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/confirm", response_model=InventoryResponse)
async def confirm_stock(
        *,
        db: AsyncSession = Depends(get_db),
        confirm_data: StockConfirmRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    确认出库，主要是为了配合stock/reserve使用来完成正确支付完成出库
    """
    inventory_service = InventoryService()

    try:
        success = await inventory_service.confirm_stock_out(
            db=db,
            reference_id=confirm_data.reference_id,
            reference_type=confirm_data.reference_type,
            notes=confirm_data.notes,
            operator_id=current_user.id
        )

        if not success:
            return InventoryResponse(
                success=False,
                message="No matching reserve transactions found",
                data=None
            )

        return InventoryResponse(
            success=True,
            message="Successfully confirmed stock out",
            data=None
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/adjust", response_model=InventoryResponse)
async def adjust_stock(
        *,
        db: AsyncSession = Depends(get_db),
        adjust_data: StockAdjustRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    库存调整(主要是用于盘点差异、数据纠错)
    """
    inventory_service = InventoryService()

    try:
        # 将reason信息整合到notes中
        combined_notes = f"原因: {adjust_data.reason}"
        if adjust_data.notes:
            combined_notes += f", 备注: {adjust_data.notes}"

        await inventory_service.adjust_stock(
            db=db,
            sku_id=adjust_data.sku_id,
            warehouse_id=adjust_data.warehouse_id,
            new_quantity=adjust_data.new_quantity,
            notes=combined_notes,
            operator_id=current_user.id
        )

        return InventoryResponse(
            success=True,
            message=f"Successfully adjusted stock to {adjust_data.new_quantity} units",
            data=None
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/bulk-adjust", response_model=InventoryResponse)
async def bulk_adjust_stock(
        *,
        db: AsyncSession = Depends(get_db),
        bulk_data: BulkStockAdjustRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    批量库存调整
    """
    inventory_service = InventoryService()
    success_count = 0
    error_messages = []

    for adjust_data in bulk_data.adjustments:
        try:
            # 将reason信息整合到notes中
            combined_notes = f"原因: {adjust_data.reason}"
            if adjust_data.notes:
                combined_notes += f", 备注: {adjust_data.notes}"

            await inventory_service.adjust_stock(
                db=db,
                sku_id=adjust_data.sku_id,
                warehouse_id=adjust_data.warehouse_id,
                new_quantity=adjust_data.new_quantity,
                notes=combined_notes,
                operator_id=current_user.id
            )
            success_count += 1
        except ValueError as e:
            error_messages.append(f"SKU {adjust_data.sku_id} in warehouse {adjust_data.warehouse_id}: {str(e)}")
        except Exception as e:
            error_messages.append(
                f"SKU {adjust_data.sku_id} in warehouse {adjust_data.warehouse_id}: An error occurred: {str(e)}")

    if success_count == len(bulk_data.adjustments):
        return InventoryResponse(
            success=True,
            message=f"Successfully adjusted stock for {success_count} items",
            data=None
        )
    else:
        return InventoryResponse(
            success=False,
            message=f"Adjusted {success_count} items, but encountered errors: {', '.join(error_messages)}",
            data=None
        )


@router.post("/stock/transfer", response_model=InventoryResponse)
async def transfer_stock(
        *,
        db: AsyncSession = Depends(get_db),
        transfer_data: StockTransferRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    库存调拨
    """
    inventory_service = InventoryService()

    try:
        await inventory_service.transfer_stock(
            db=db,
            sku_id=transfer_data.sku_id,
            from_warehouse_id=transfer_data.source_warehouse_id,
            to_warehouse_id=transfer_data.target_warehouse_id,
            quantity=transfer_data.quantity,
            notes=transfer_data.notes,
            operator_id=current_user.id
        )

        return InventoryResponse(
            success=True,
            message=f"Successfully transferred {transfer_data.quantity} units between warehouses",
            data=None
        )
    except ValueError as e:
        return InventoryResponse(
            success=False,
            message=str(e),
            data=None
        )
    except Exception as e:
        return InventoryResponse(
            success=False,
            message=f"An error occurred: {str(e)}",
            data=None
        )


@router.post("/stock/bulk-transfer", response_model=InventoryResponse)
async def bulk_transfer_stock(
        *,
        db: AsyncSession = Depends(get_db),
        bulk_data: BulkStockTransferRequest,
        _: User = Depends(has_permission("inventory:manage")),
        current_user: User = Depends(get_current_user)
):
    """
    批量调拨库存
    """
    inventory_service = InventoryService()
    success_count = 0
    error_messages = []

    for transfer_data in bulk_data.transfers:
        try:
            await inventory_service.transfer_stock(
                db=db,
                sku_id=transfer_data.sku_id,
                from_warehouse_id=transfer_data.source_warehouse_id,
                to_warehouse_id=transfer_data.target_warehouse_id,
                quantity=transfer_data.quantity,
                notes=transfer_data.notes,
                operator_id=current_user.id
            )
            success_count += 1
        except ValueError as e:
            error_messages.append(
                f"SKU {transfer_data.sku_id} from warehouse {transfer_data.source_warehouse_id} to {transfer_data.target_warehouse_id}: {str(e)}")
        except Exception as e:
            error_messages.append(
                f"SKU {transfer_data.sku_id} from warehouse {transfer_data.source_warehouse_id} to {transfer_data.target_warehouse_id}: An error occurred: {str(e)}")

    if success_count == len(bulk_data.transfers):
        return InventoryResponse(
            success=True,
            message=f"Successfully transferred stock for {success_count} items",
            data=None
        )
    else:
        return InventoryResponse(
            success=False,
            message=f"Transferred {success_count} items, but encountered errors: {', '.join(error_messages)}",
            data=None
        )


@router.get("/low-stock-alerts", response_model=LowStockAlertResponse)
async def get_low_stock_alerts(
        *,
        db: AsyncSession = Depends(get_db),
        warehouse_id: Optional[int] = Query(None),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    按需手动获取低库存预警
    """
    inventory_service = InventoryService()

    try:
        low_stock_items = await inventory_service.get_low_stock_items(db=db, warehouse_id=warehouse_id)

        # 获取所有产品ID
        product_ids = [item['product_id'] for item in low_stock_items]

        # 查询产品信息
        product_query = select(Product).where(Product.id.in_(product_ids))
        result = await db.execute(product_query)
        products = {product.id: product for product in result.scalars().all()}

        # 格式化数据
        alerts = []
        for item in low_stock_items:
            # 获取产品名称
            product_name = products.get(item['product_id']).name if item['product_id'] in products else ""

            alert = LowStockAlert(
                inventory_item_id=item['id'],
                sku_id=item['sku_id'],
                sku_code=item['sku_code'],
                product_id=item['product_id'],
                product_name=product_name,
                warehouse_id=item['warehouse_id'],
                warehouse_name=item['warehouse_name'],
                current_quantity=item['quantity'],
                reserved_quantity=item['reserved_quantity'],
                available_quantity=item['available_quantity'],
                alert_threshold=item['alert_threshold']
            )
            alerts.append(alert)

        return LowStockAlertResponse(
            items=alerts,
            total=len(alerts)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )
