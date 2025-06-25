from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User
from app.models.rbac import Role
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="用户注册")
async def create_user(
        user_in: UserCreate, db: AsyncSession = Depends(get_db)
) -> User:
    """
    创建新用户
    """
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被使用",
        )

    # 创建新用户
    user = User(
        email=user_in.email,
        username=user_in.username,
        password=get_password_hash(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 为新用户分配"普通用户"角色
    # 查询普通用户角色
    result = await db.execute(select(Role).where(Role.name == "普通用户"))
    normal_user_role = result.scalars().first()

    if normal_user_role:
        # 创建关联关系
        # 使用SQL直接插入关联记录，避免懒加载问题
        from sqlalchemy import text
        await db.execute(
            text("INSERT INTO user_role (user_id, role_id) VALUES (:user_id, :role_id)"),
            {"user_id": user.id, "role_id": normal_user_role.id}
        )
        await db.commit()

        # 重新加载用户，确保关系被正确加载
        user_query = select(User).where(User.id == user.id).options(selectinload(User.roles))
        result = await db.execute(user_query)
        user = result.scalars().first()

    return user
