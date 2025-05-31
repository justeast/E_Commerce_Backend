"""
api依赖项
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.security import SECRET_KEY, ALGORITHM, is_token_blacklisted
from app.core.redis_client import get_redis_pool
from app.db.session import get_db
from app.models.rbac import Role
from app.models.user import User
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
        redis_pool=Depends(get_redis_pool)
) -> User:
    """
    获取当前用户
    """
    # 检查令牌是否在黑名单中
    if await is_token_blacklisted(token, redis_pool):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # 验证令牌类型
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌类型",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_data = TokenData(sub=user_id, type=token_type)
    except PyJWTError:
        raise credentials_exception

    # 预加载用户角色，避免后续惰性加载
    result = await db.execute(select(User).where(User.id == token_data.sub).options(selectinload(User.roles)))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    return user


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    获取当前有效用户
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    return current_user


def has_permission(required_permission: str):
    """
    检查用户是否有特定权限
    """

    async def permission_dependency(
            current_user: Annotated[User, Depends(get_current_user)],
            db: AsyncSession = Depends(get_db)
    ) -> User:
        # 获取用户的所有角色和权限（使用selectinload预加载关系）
        user_query = select(User).where(User.id == current_user.id).options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
        result = await db.execute(user_query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        # 检查用户的角色是否有所需权限
        has_required_permission = False
        for role in user.roles:
            for permission in role.permissions:
                if permission.code == required_permission:
                    has_required_permission = True
                    break
            if has_required_permission:
                break

        if not has_required_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )

        return user

    return permission_dependency


def has_role(required_role: str):
    """
    检查用户是否有特定角色
    """

    async def role_dependency(
            current_user: Annotated[User, Depends(get_current_user)],
            db: AsyncSession = Depends(get_db)
    ) -> User:
        # 获取用户的所有角色（使用selectinload预加载关系）
        user_query = select(User).where(User.id == current_user.id).options(
            selectinload(User.roles)
        )
        result = await db.execute(user_query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        # 检查用户是否有所需角色
        has_required_role = False
        for role in user.roles:
            if role.name == required_role:
                has_required_role = True
                break

        if not has_required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="角色权限不足",
            )

        return user

    return role_dependency
