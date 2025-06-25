from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.api.deps import get_db, has_permission
from app.models.user import User
from app.models.inventory import Warehouse
from app.schemas.inventory import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    WarehousesResponse
)

router = APIRouter()


@router.post("/", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED, summary="创建仓库")
async def create_warehouse(
        *,
        db: AsyncSession = Depends(get_db),
        warehouse_in: WarehouseCreate,
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    创建仓库
    """
    # 检查是否已存在同名仓库
    query = select(Warehouse).where(Warehouse.name == warehouse_in.name)
    result = await db.execute(query)
    existing_warehouse = result.scalars().first()

    if existing_warehouse:
        return WarehouseResponse(
            success=False,
            message=f"Warehouse with name '{warehouse_in.name}' already exists",
            data=None
        )

    # 创建新仓库
    db_warehouse = Warehouse(**warehouse_in.model_dump())
    db.add(db_warehouse)
    await db.commit()
    await db.refresh(db_warehouse)

    return WarehouseResponse(
        success=True,
        message="Warehouse created successfully",
        data=db_warehouse
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse, summary="获取单个仓库详情")
async def get_warehouse(
        *,
        db: AsyncSession = Depends(get_db),
        warehouse_id: int = Path(..., gt=0),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    获取单个仓库详情
    """
    query = select(Warehouse).where(Warehouse.id == warehouse_id)
    result = await db.execute(query)
    warehouse = result.scalars().first()

    if not warehouse:
        return WarehouseResponse(
            success=False,
            message=f"Warehouse with ID {warehouse_id} not found",
            data=None
        )

    return WarehouseResponse(
        success=True,
        message="Warehouse retrieved successfully",
        data=warehouse
    )


@router.get("/", response_model=WarehousesResponse, summary="获取所有仓库")
async def list_warehouses(
        *,
        db: AsyncSession = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        is_active: Optional[bool] = Query(None),
        name: Optional[str] = Query(None),
        _: User = Depends(has_permission("inventory:read"))
):
    """
    获取所有仓库
    """
    query = select(Warehouse)
    count_query = select(func.count()).select_from(Warehouse)

    if is_active is not None:
        query = query.where(Warehouse.is_active == is_active)
        count_query = count_query.where(Warehouse.is_active == is_active)

    if name:
        query = query.where(Warehouse.name.ilike(f"%{name}%"))
        count_query = count_query.where(Warehouse.name.ilike(f"%{name}%"))

    # total count
    result = await db.execute(count_query)
    total = result.scalar()

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    warehouses = result.scalars().all()

    return WarehousesResponse(
        success=True,
        message="Warehouses retrieved successfully",
        data=list(warehouses),
        total=total,
        page=skip // limit + 1,
        size=limit
    )


@router.put("/{warehouse_id}", response_model=WarehouseResponse, summary="更新仓库信息")
async def update_warehouse(
        *,
        db: AsyncSession = Depends(get_db),
        warehouse_id: int = Path(..., gt=0),
        warehouse_in: WarehouseUpdate,
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    更新仓库
    """
    query = select(Warehouse).where(Warehouse.id == warehouse_id)
    result = await db.execute(query)
    warehouse = result.scalars().first()

    if not warehouse:
        return WarehouseResponse(
            success=False,
            message=f"Warehouse with ID {warehouse_id} not found",
            data=None
        )

    # 检查是否更新了 name 以及新 name 是否已存在
    if warehouse_in.name and warehouse_in.name != warehouse.name:
        name_query = select(Warehouse).where(
            Warehouse.name == warehouse_in.name,
            Warehouse.id != warehouse_id
        )
        name_result = await db.execute(name_query)
        existing_warehouse = name_result.scalars().first()

        if existing_warehouse:
            return WarehouseResponse(
                success=False,
                message=f"Warehouse with name '{warehouse_in.name}' already exists",
                data=None
            )

    # 更新仓库信息
    update_data = warehouse_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(warehouse, field, value)

    await db.commit()
    await db.refresh(warehouse)

    return WarehouseResponse(
        success=True,
        message="Warehouse updated successfully",
        data=warehouse
    )


@router.delete("/{warehouse_id}", response_model=WarehouseResponse, summary="删除仓库")
async def delete_warehouse(
        *,
        db: AsyncSession = Depends(get_db),
        warehouse_id: int = Path(..., gt=0),
        _: User = Depends(has_permission("inventory:manage"))
):
    """
    删除仓库（只是软删除，is_active 设置为 False）
    """
    query = select(Warehouse).where(Warehouse.id == warehouse_id)
    result = await db.execute(query)
    warehouse = result.scalars().first()

    if not warehouse:
        return WarehouseResponse(
            success=False,
            message=f"Warehouse with ID {warehouse_id} not found",
            data=None
        )

    warehouse.is_active = False
    await db.commit()

    return WarehouseResponse(
        success=True,
        message="Warehouse deleted successfully",
        data=warehouse
    )
