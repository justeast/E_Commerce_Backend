from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.user_profile import UserProfileTagRead
from app.services.user_profile_service import user_profile_service

router = APIRouter()


@router.get(
    "/",
    response_model=List[UserProfileTagRead],
    summary="获取当前用户画像标签",
)
async def read_user_profile(
        db: AsyncSession = Depends(deps.get_db),
        current_user=Depends(deps.get_current_active_user),
        tag_key: str | None = None,
        limit: int | None = None,
):
    return await user_profile_service.get_user_tags(
        db=db, user_id=current_user.id, tag_key=tag_key, limit=limit
    )
