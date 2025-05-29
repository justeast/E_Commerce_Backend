from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.rbac import Role, Permission
from app.models.user import User
from app.schemas.rbac import (
    Permission as PermissionSchema,
    PermissionCreate,
    PermissionUpdate,
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate,
    UserRoleUpdate,
    UserWithRoles,
)

router = APIRouter()


# 权限相关端点
@router.get("/permissions", response_model=List[PermissionSchema])
async def list_permissions(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
):
    """
    获取权限列表
    """
    result = await db.execute(select(Permission).offset(skip).limit(limit))
    permissions = result.scalars().all()
    return permissions


@router.post("/permissions", response_model=PermissionSchema, status_code=status.HTTP_201_CREATED)
async def create_permission(
        permission: PermissionCreate,
        db: AsyncSession = Depends(get_db)
):
    """
    创建新权限
    """
    # 检查权限名称和代码是否已存在
    result = await db.execute(
        select(Permission).where(
            (Permission.name == permission.name) | (Permission.code == permission.code)
        )
    )
    existing_permission = result.scalars().first()
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限名称或代码已存在",
        )

    # 创建新权限
    db_permission = Permission(
        name=permission.name,
        code=permission.code,
        description=permission.description,
    )
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)
    return db_permission


@router.get("/permissions/{permission_id}", response_model=PermissionSchema)
async def get_permission(
        permission_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    获取特定权限
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalars().first()
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")
    return permission


@router.put("/permissions/{permission_id}", response_model=PermissionSchema)
async def update_permission(
        permission_id: int,
        permission_update: PermissionUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    更新权限
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    db_permission = result.scalars().first()
    if db_permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")

    # 更新权限字段
    update_data = permission_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_permission, key, value)

    await db.commit()
    await db.refresh(db_permission)
    return db_permission


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
        permission_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    删除权限
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalars().first()
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")

    await db.delete(permission)
    await db.commit()
    return None


# 角色相关端点
@router.get("/roles", response_model=List[RoleSchema])
async def list_roles(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """
    获取角色列表
    """
    # 使用selectinload预加载permissions关系，避免延迟加载问题
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).offset(skip).limit(limit)
    )
    roles = result.scalars().all()

    return roles


@router.post("/roles", response_model=RoleSchema, status_code=status.HTTP_201_CREATED)
async def create_role(
        role: RoleCreate,
        db: AsyncSession = Depends(get_db)
):
    """
    创建新角色
    """
    # 检查角色名称是否已存在
    result = await db.execute(select(Role).where(Role.name == role.name))
    existing_role = result.scalars().first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名称已存在",
        )

    # 创建新角色
    db_role = Role(
        name=role.name,
        description=role.description,
    )

    # 如果提供了权限ID，添加权限关联
    if role.permission_ids:
        for permission_id in role.permission_ids:
            result = await db.execute(select(Permission).where(Permission.id == permission_id))
            permission = result.scalars().first()
            if permission:
                db_role.permissions.append(permission)

    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)

    # 显式刷新permissions关系，确保返回完整数据
    await db.refresh(db_role, ["permissions"])
    return db_role


@router.get("/roles/{role_id}", response_model=RoleSchema)
async def get_role(
        role_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    获取特定角色
    """
    # 预加载permissions关系
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    role = result.scalars().first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return role


@router.put("/roles/{role_id}", response_model=RoleSchema)
async def update_role(
        role_id: int,
        role_update: RoleUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    更新角色
    """
    # 预加载permissions关系
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    db_role = result.scalars().first()
    if db_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 更新角色字段
    update_data = role_update.model_dump(exclude_unset=True, exclude={"permission_ids"})
    for key, value in update_data.items():
        setattr(db_role, key, value)

    # 更新权限关联
    if role_update.permission_ids is not None:
        # 清除现有权限
        db_role.permissions = []

        # 添加新权限
        for permission_id in role_update.permission_ids:
            result = await db.execute(select(Permission).where(Permission.id == permission_id))
            permission = result.scalars().first()
            if permission:
                db_role.permissions.append(permission)

    await db.commit()
    await db.refresh(db_role)
    return db_role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
        role_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    删除角色
    """
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalars().first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    await db.delete(role)
    await db.commit()
    return None


# 用户角色相关端点
@router.get("/users/{user_id}/roles", response_model=List[RoleSchema])
async def get_user_roles(
        user_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    获取用户的角色列表
    """
    # 预加载roles关系
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 为每个角色预加载permissions关系
    for role in user.roles:
        await db.refresh(role, ["permissions"])

    return user.roles


@router.get("/users/roles", response_model=List[UserWithRoles])
async def list_users_with_roles(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """
    获取所有用户及其角色列表
    """
    # 预加载roles关系
    result = await db.execute(
        select(User).options(selectinload(User.roles)).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    user_role_list = []
    for user in users:
        # 为每个角色预加载permissions关系
        for role in user.roles:
            await db.refresh(role, ["permissions"])

        # 创建UserWithRoles模型实例
        user_with_roles = UserWithRoles(
            user_id=user.id,
            email=user.email,
            is_active=user.is_active,
            roles=user.roles
        )
        user_role_list.append(user_with_roles)

    return user_role_list


@router.put("/users/{user_id}/roles", status_code=status.HTTP_200_OK)
async def update_user_roles(
        user_id: int,
        user_role_update: UserRoleUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    更新用户的角色
    """
    # 检查用户是否存在
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 清除现有角色
    user.roles = []

    # 添加新角色
    for role_id in user_role_update.role_ids:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalars().first()
        if role:
            user.roles.append(role)

    await db.commit()
    return {"message": "用户角色已更新"}
