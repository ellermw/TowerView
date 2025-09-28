from pydantic import BaseModel, Field, validator
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


class LocalUserCreate(BaseModel):
    """Schema for creating a local user"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=8)
    must_change_password: bool = False
    role: Optional[str] = None  # 'admin', 'staff', or 'support'


class LocalUserUpdate(BaseModel):
    """Schema for updating a local user"""
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    must_change_password: Optional[bool] = None


class UserRoleUpdate(BaseModel):
    """Schema for updating a user's role"""
    role: str = Field(..., pattern="^(admin|staff|support)$")


class UserPermissionSchema(BaseModel):
    """Schema for user permissions"""
    server_id: int
    can_view_sessions: bool = True
    can_view_users: bool = True
    can_view_analytics: bool = True
    can_terminate_sessions: bool = False
    can_manage_server: bool = False

    class Config:
        from_attributes = True


class UserPermissionUpdate(BaseModel):
    """Schema for updating user permissions"""
    can_view_sessions: Optional[bool] = None
    can_view_users: Optional[bool] = None
    can_view_analytics: Optional[bool] = None
    can_terminate_sessions: Optional[bool] = None
    can_manage_server: Optional[bool] = None


class LocalUserResponse(UserBase):
    """Response schema for local users"""
    id: int
    type: UserType
    email: Optional[str] = None
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    permissions: List[UserPermissionSchema] = []

    class Config:
        from_attributes = True