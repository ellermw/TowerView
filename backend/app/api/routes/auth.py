from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import verify_token
from ...schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, ChangePasswordRequest
from ...services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login with either admin credentials or media user credentials"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Login request received: admin={bool(login_data.admin_login)}, media={bool(login_data.media_login)}, local={bool(login_data.local_login)}")
    if login_data.admin_login:
        logger.info(f"Admin login attempt: {login_data.admin_login.username}")
    if login_data.local_login:
        logger.info(f"Local login attempt: {login_data.local_login.username}")
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

    elif login_data.local_login:
        # Local user login
        from ...models.user import UserType
        user = auth_service.authenticate_local_user(
            login_data.local_login.username,
            login_data.local_login.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid local user credentials"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either admin_login, media_login, or local_login"
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


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Change password for the current user"""
    from ...core.security import verify_password, get_password_hash, verify_token
    from ...models.user import UserType

    # Get token from header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Get user
    from ...services.user_service import UserService
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate new passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )

    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    user.must_change_password = False
    db.commit()

    return {"message": "Password changed successfully"}


@router.get("/me")
async def get_current_user_info(
    current_user = Depends(lambda: None)  # This will be implemented properly later
):
    """Get current user information"""
    from ...core.security import get_current_user
    from ...schemas.user import UserResponse
    # TODO: Implement properly with dependency injection
    return {"message": "User info endpoint - to be implemented"}