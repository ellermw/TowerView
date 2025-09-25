from pydantic import BaseModel, Field
from typing import Optional
from ..models.user import ProviderType


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class MediaLoginRequest(BaseModel):
    server_id: int
    provider: ProviderType
    username: str
    password: str


class LoginRequest(BaseModel):
    admin_login: Optional[AdminLoginRequest] = None
    media_login: Optional[MediaLoginRequest] = None

    class Config:
        extra = "forbid"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    must_change_password: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str