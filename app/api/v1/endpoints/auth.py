from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import jwt
from typing import Optional

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    add_token_to_blacklist,
    is_token_blacklisted
)
from app.core.redis_client import get_redis_pool
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, Login, RefreshToken

router = APIRouter()


@router.post("/login", response_model=Token, summary="用户登录")
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


@router.post("/refresh", response_model=Token, summary="刷新访问token")
async def refresh_access_token(
        refresh_token_data: RefreshToken,
        db: AsyncSession = Depends(get_db),
        redis_pool=Depends(get_redis_pool)
):
    """
    使用刷新令牌获取新的访问令牌
    """
    try:
        # 检查刷新令牌是否在黑名单中
        if await is_token_blacklisted(refresh_token_data.refresh_token, redis_pool):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已失效，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )

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


@router.post("/logout", status_code=status.HTTP_200_OK, summary="用户退出登录")
async def logout(
        authorization: Optional[str] = Header(None),
        refresh_token: Optional[RefreshToken] = None,
        redis_pool=Depends(get_redis_pool)
):
    """
    退出登录

    将当前的访问令牌和刷新令牌（如果提供）添加到黑名单中，使它们失效
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供授权信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 从授权头中提取访问令牌
        scheme, access_token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证方案",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 将访问令牌添加到Redis黑名单
        await add_token_to_blacklist(access_token, redis_pool)

        # 如果提供了刷新令牌，也将其添加到Redis黑名单
        if refresh_token:
            await add_token_to_blacklist(refresh_token.refresh_token, redis_pool)

        return {"detail": "退出登录成功"}

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的授权信息格式",
            headers={"WWW-Authenticate": "Bearer"},
        )
