from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import verify_token
from ...schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest
from ...services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login with either admin credentials or media user credentials"""
    auth_service = AuthService(db)

    if login_data.admin_login:
        user = await auth_service.authenticate_admin(login_data.admin_login)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )

    elif login_data.media_login:
        user = await auth_service.authenticate_media_user(login_data.media_login)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid media user credentials"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either admin_login or media_login"
        )

    return auth_service.create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    payload = verify_token(refresh_data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user and create new tokens
    from ...services.user_service import UserService
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    auth_service = AuthService(db)
    return auth_service.create_tokens(user)


@router.post("/logout")
async def logout():
    """Logout (client should discard tokens)"""
    return {"message": "Logout successful"}


@router.get("/me")
async def get_current_user_info(
    current_user = Depends(lambda: None)  # This will be implemented properly later
):
    """Get current user information"""
    from ...core.security import get_current_user
    from ...schemas.user import UserResponse
    # TODO: Implement properly with dependency injection
    return {"message": "User info endpoint - to be implemented"}