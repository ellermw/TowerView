from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..models.user import UserType, ProviderType


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None


class UserCreate(UserBase):
    type: UserType
    provider: Optional[ProviderType] = None
    provider_user_id: Optional[str] = None
    server_id: Optional[int] = None
    password: Optional[str] = None  # Only for admin users


class UserResponse(UserBase):
    id: int
    type: UserType
    provider: Optional[ProviderType] = None
    provider_user_id: Optional[str] = None
    server_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServerUserResponse(BaseModel):
    """Schema for users from providers (not stored in database)"""
    user_id: str
    username: str
    email: Optional[str] = None
    thumb: Optional[str] = None
    admin: bool = False
    disabled: bool = False
    hidden: bool = False
    restricted: bool = False
    protected: bool = False
    guest: bool = False
    home: bool = False
    last_activity: Optional[str] = None
    last_login: Optional[str] = None

    # Server info (added by API)
    server_name: Optional[str] = None
    server_id: Optional[int] = None
    server_type: Optional[str] = None