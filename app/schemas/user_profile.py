from datetime import datetime
from pydantic import BaseModel


class UserProfileTagBase(BaseModel):
    tag_key: str
    tag_value: str
    weight: float = 1.0


class UserProfileTagCreate(UserProfileTagBase):
    user_id: int


class UserProfileTagRead(UserProfileTagBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True
