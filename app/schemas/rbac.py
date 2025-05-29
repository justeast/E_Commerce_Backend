from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# 权限模型
class PermissionBase(BaseModel):
    """权限基础模型"""
    name: str = Field(..., description="权限名称")
    code: str = Field(..., description="权限代码")
    description: Optional[str] = Field(None, description="权限描述")


class PermissionCreate(PermissionBase):
    """创建权限请求模型"""
    pass


class PermissionUpdate(BaseModel):
    """更新权限请求模型"""
    name: Optional[str] = Field(None, description="权限名称")
    code: Optional[str] = Field(None, description="权限代码")
    description: Optional[str] = Field(None, description="权限描述")


class PermissionInDB(PermissionBase):
    """数据库中的权限模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Permission(PermissionInDB):
    """权限响应模型"""
    pass


# 角色模型
class RoleBase(BaseModel):
    """角色基础模型"""
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")


class RoleCreate(RoleBase):
    """创建角色请求模型"""
    permission_ids: Optional[List[int]] = Field(None, description="权限ID列表")


class RoleUpdate(BaseModel):
    """更新角色请求模型"""
    name: Optional[str] = Field(None, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    permission_ids: Optional[List[int]] = Field(None, description="权限ID列表")


class RoleInDB(RoleBase):
    """数据库中的角色模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Role(RoleInDB):
    """角色响应模型"""
    permissions: List[Permission] = Field([], description="角色拥有的权限列表")


# 用户角色关联模型
class UserRoleUpdate(BaseModel):
    """更新用户角色关联请求模型"""
    role_ids: List[int] = Field(..., description="角色ID列表")


# 用户角色信息模型
class UserWithRoles(BaseModel):
    """用户及其角色信息响应模型"""
    user_id: int = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    is_active: bool = Field(..., description="是否激活")
    roles: List[Role] = Field([], description="用户拥有的角色列表")

    class Config:
        from_attributes = True
