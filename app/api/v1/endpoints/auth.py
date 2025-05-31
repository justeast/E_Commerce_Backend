from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import jwt

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, Login, RefreshToken

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(
        form_data: Login, db: AsyncSession = Depends(get_db)
):
    """
    用户登录获取令牌
    """
    # 查询用户
    result = await db.execute(
        select(User).where(
            (User.username == form_data.username_or_email) | (User.email == form_data.username_or_email)
        ).options(selectinload(User.roles))  # 预加载角色避免懒加载问题
    )
    user = result.scalars().first()

    # 验证用户和密码
    if not user or not verify_password(form_data.password, str(user.password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

    # 创建刷新令牌
    refresh_token = create_refresh_token(subject=str(user.id))

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
        refresh_token_data: RefreshToken,
        db: AsyncSession = Depends(get_db)
):
    """
    使用刷新令牌获取新的访问令牌
    """
    try:
        # 解码刷新令牌
        payload = decode_token(refresh_token_data.refresh_token)

        # 验证令牌类型
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 获取用户ID
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌数据",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 查询用户
        result = await db.execute(
            select(User).where(User.id == int(user_id)).options(selectinload(User.roles))
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被删除",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 创建新的访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        )

        # 返回新的访问令牌和原刷新令牌
        return {
            "access_token": access_token,
            "refresh_token": refresh_token_data.refresh_token,
            "token_type": "bearer"
        }

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已过期或无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
