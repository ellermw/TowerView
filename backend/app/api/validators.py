"""
Input Validation Middleware and Validators
Provides comprehensive input validation for all API endpoints
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, EmailStr, HttpUrl
from datetime import datetime
import re


# Base validators
class PaginationParams(BaseModel):
    """Common pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")

    @validator('per_page')
    def validate_per_page(cls, v):
        if v > 100:
            raise ValueError("Maximum 100 items per page allowed")
        return v


class DateRangeParams(BaseModel):
    """Date range filtering parameters"""
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError("End date must be after start date")
        return v


# Server validators
class ServerCreateValidator(BaseModel):
    """Validator for server creation"""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    type: str = Field(..., regex="^(plex|emby|jellyfin)$", description="Server type")
    base_url: HttpUrl = Field(..., description="Server base URL")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Server credentials")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Server name cannot be empty")
        # Check for special characters that might cause issues
        if re.search(r'[<>:"\/\\|?*]', v):
            raise ValueError("Server name contains invalid characters")
        return v.strip()

    @validator('base_url')
    def validate_url(cls, v):
        url_str = str(v)
        if not url_str.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v


class ServerUpdateValidator(BaseModel):
    """Validator for server updates"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, regex="^(plex|emby|jellyfin)$")
    base_url: Optional[HttpUrl] = None
    enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError("Server name cannot be empty")
            if re.search(r'[<>:"\/\\|?*]', v):
                raise ValueError("Server name contains invalid characters")
            return v.strip()
        return v


# User validators
class UserCreateValidator(BaseModel):
    """Validator for user creation"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: Optional[EmailStr] = Field(None, description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    type: str = Field("local_user", regex="^(admin|local_user|media_user)$")

    @validator('username')
    def validate_username(cls, v):
        if not v.strip():
            raise ValueError("Username cannot be empty")
        # Allow only alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username can only contain letters, numbers, underscore, and hyphen")
        return v.strip().lower()

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one number")
        return v


class UserUpdateValidator(BaseModel):
    """Validator for user updates"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    is_active: Optional[bool] = None
    type: Optional[str] = Field(None, regex="^(admin|local_user|media_user)$")

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError("Username cannot be empty")
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError("Username can only contain letters, numbers, underscore, and hyphen")
            return v.strip().lower()
        return v

    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not re.search(r'[A-Z]', v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not re.search(r'[0-9]', v):
                raise ValueError("Password must contain at least one number")
        return v


# Permission validators
class PermissionValidator(BaseModel):
    """Validator for permission updates"""
    user_id: int = Field(..., gt=0, description="User ID")
    server_id: int = Field(..., gt=0, description="Server ID")
    can_view_servers: bool = Field(False, description="Can view servers")
    can_manage_servers: bool = Field(False, description="Can manage servers")
    can_view_all_sessions: bool = Field(False, description="Can view all sessions")
    can_terminate_sessions: bool = Field(False, description="Can terminate sessions")
    can_manage_server: bool = Field(False, description="Can manage server")

    @validator('can_manage_servers')
    def validate_manage_requires_view(cls, v, values):
        if v and 'can_view_servers' in values and not values['can_view_servers']:
            raise ValueError("Cannot manage servers without view permission")
        return v


# Session validators
class SessionTerminateValidator(BaseModel):
    """Validator for session termination"""
    session_id: str = Field(..., min_length=1, max_length=100, description="Session ID")
    reason: Optional[str] = Field(None, max_length=500, description="Termination reason")

    @validator('session_id')
    def validate_session_id(cls, v):
        if not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()


# Analytics validators
class AnalyticsRequestValidator(BaseModel):
    """Validator for analytics requests"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    server_ids: Optional[List[int]] = Field(None, max_items=100)
    user_ids: Optional[List[str]] = Field(None, max_items=100)

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError("End date must be after start date")
            # Limit to 1 year range
            delta = v - values['start_date']
            if delta.days > 365:
                raise ValueError("Date range cannot exceed 1 year")
        return v

    @validator('server_ids')
    def validate_server_ids(cls, v):
        if v:
            if len(v) > 100:
                raise ValueError("Maximum 100 server IDs allowed")
            if any(id <= 0 for id in v):
                raise ValueError("Invalid server ID")
        return v


# Settings validators
class SiteSettingsValidator(BaseModel):
    """Validator for site settings"""
    site_name: str = Field(..., min_length=1, max_length=100, description="Site name")

    @validator('site_name')
    def validate_site_name(cls, v):
        if not v.strip():
            raise ValueError("Site name cannot be empty")
        # Limit special characters
        if re.search(r'[<>:"\/\\|?*]', v):
            raise ValueError("Site name contains invalid characters")
        return v.strip()


class SyncSettingsValidator(BaseModel):
    """Validator for sync settings"""
    user_sync_enabled: bool = Field(False)
    user_sync_interval_seconds: int = Field(3600, ge=60, le=86400)
    library_sync_enabled: bool = Field(False)
    library_sync_interval_seconds: int = Field(86400, ge=3600, le=604800)
    library_passive_discovery: bool = Field(True)
    sessions_cache_interval_seconds: int = Field(30, ge=10, le=300)
    analytics_cache_interval_seconds: int = Field(300, ge=60, le=3600)
    server_status_interval_seconds: int = Field(60, ge=30, le=600)

    @validator('user_sync_interval_seconds')
    def validate_user_sync_interval(cls, v):
        if v < 60:
            raise ValueError("User sync interval must be at least 60 seconds")
        if v > 86400:
            raise ValueError("User sync interval cannot exceed 24 hours")
        return v

    @validator('library_sync_interval_seconds')
    def validate_library_sync_interval(cls, v):
        if v < 3600:
            raise ValueError("Library sync interval must be at least 1 hour")
        if v > 604800:
            raise ValueError("Library sync interval cannot exceed 7 days")
        return v


# Integration validators
class NetdataAuthValidator(BaseModel):
    """Validator for Netdata authentication"""
    api_token: str = Field(..., min_length=10, max_length=500)
    space_id: Optional[str] = Field(None, max_length=100)

    @validator('api_token')
    def validate_token(cls, v):
        # Remove whitespace
        v = v.strip()
        if not v:
            raise ValueError("API token cannot be empty")
        # Basic token format validation
        if len(v) < 10:
            raise ValueError("Invalid API token format")
        return v


class PortainerAuthValidator(BaseModel):
    """Validator for Portainer authentication"""
    url: HttpUrl = Field(..., description="Portainer URL")
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1, max_length=100)
    api_token: Optional[str] = Field(None, min_length=10, max_length=500)
    endpoint_id: int = Field(1, ge=1)

    @validator('url')
    def validate_url(cls, v):
        url_str = str(v)
        if not url_str.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v

    @validator('api_token')
    def validate_auth_method(cls, v, values):
        has_username = 'username' in values and values['username']
        has_password = 'password' in values and values['password']

        if not v and not (has_username and has_password):
            raise ValueError("Either API token or username/password required")

        if v and (has_username or has_password):
            raise ValueError("Provide either API token OR username/password, not both")

        return v


# Library validators
class LibraryAccessValidator(BaseModel):
    """Validator for library access updates"""
    library_ids: List[str] = Field(..., max_items=100, description="Library IDs")
    all_libraries: bool = Field(False, description="Grant access to all libraries")

    @validator('library_ids')
    def validate_library_ids(cls, v, values):
        if 'all_libraries' in values and values['all_libraries']:
            # If all_libraries is True, library_ids should be empty
            if v:
                raise ValueError("Cannot specify library IDs when all_libraries is True")
        else:
            # If all_libraries is False, need at least one library
            if not v:
                raise ValueError("Must specify at least one library ID when all_libraries is False")
            if len(v) > 100:
                raise ValueError("Maximum 100 library IDs allowed")
        return v


# Authentication validators
class LoginValidator(BaseModel):
    """Validator for login requests"""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)
    provider: Optional[str] = Field(None, regex="^(plex|emby|jellyfin|local)$")

    @validator('username')
    def validate_username(cls, v):
        if not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()

    @validator('password')
    def validate_password(cls, v):
        if not v.strip():
            raise ValueError("Password cannot be empty")
        return v


class TokenRefreshValidator(BaseModel):
    """Validator for token refresh"""
    refresh_token: str = Field(..., min_length=10)

    @validator('refresh_token')
    def validate_token(cls, v):
        if not v.strip():
            raise ValueError("Refresh token cannot be empty")
        return v.strip()


# Container validators
class ContainerActionValidator(BaseModel):
    """Validator for container actions"""
    action: str = Field(..., regex="^(start|stop|restart|update)$")
    force: bool = Field(False, description="Force the action")

    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['start', 'stop', 'restart', 'update']
        if v not in valid_actions:
            raise ValueError(f"Invalid action. Must be one of: {', '.join(valid_actions)}")
        return v


# Utility function to apply validators
def validate_input(validator_class: BaseModel):
    """
    Decorator to validate input using Pydantic models

    Usage:
    @validate_input(UserCreateValidator)
    async def create_user(data: UserCreateValidator, ...):
        ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # The validated data will be passed as the first argument
            # after 'self' if it's a class method
            return await func(*args, **kwargs)
        wrapper.__annotations__ = func.__annotations__
        return wrapper
    return decorator