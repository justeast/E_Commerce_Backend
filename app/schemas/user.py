from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """用户基础模型"""
    email: EmailStr
    username: str


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        """验证密码复杂度：必须包含数字和大小写字母"""
        # 检查是否只包含数字
        if v.isdigit():
            raise ValueError("密码必须包含大小写字母")

        # 其他验证
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        return v


class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    """用户响应模型"""
    pass
