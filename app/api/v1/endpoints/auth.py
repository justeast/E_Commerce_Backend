from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, Login

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
        )
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

    return {"access_token": access_token, "token_type": "bearer"}
