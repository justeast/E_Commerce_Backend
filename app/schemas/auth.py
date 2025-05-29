from pydantic import BaseModel, Field


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """令牌数据模型"""
    sub: str = None


class Login(BaseModel):
    """登录模型"""
    username_or_email: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")