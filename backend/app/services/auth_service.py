from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from ..core.config import settings
from ..models.user import User, UserType, ProviderType
from ..models.server import Server
from ..schemas.auth import AdminLoginRequest, MediaLoginRequest, TokenResponse
from .user_service import UserService
from ..providers.factory import ProviderFactory


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)

    async def authenticate_admin(self, login_data: AdminLoginRequest) -> Optional[User]:
        user = self.db.query(User).filter(
            User.username == login_data.username,
            User.type == UserType.admin
        ).first()

        if not user or not verify_password(login_data.password, user.password_hash):
            return None

        # Update last login time
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        return user

    async def authenticate_media_user(self, login_data: MediaLoginRequest) -> Optional[User]:
        # Get the server
        server = self.db.query(Server).filter(
            Server.id == login_data.server_id,
            Server.type.name == login_data.provider.value,
            Server.enabled == True
        ).first()

        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found or disabled"
            )

        # Authenticate with the provider
        try:
            provider = ProviderFactory.create_provider(server)
            auth_result = await provider.authenticate_user(
                login_data.username,
                login_data.password
            )

            if not auth_result:
                return None

            provider_user_id = auth_result.get("user_id")
            user_email = auth_result.get("email")

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider authentication failed: {str(e)}"
            )

        # Find or create the media user
        user = self.db.query(User).filter(
            User.provider_user_id == provider_user_id,
            User.server_id == server.id,
            User.type == UserType.media_user
        ).first()

        if not user:
            # Create new media user
            user = User(
                type=UserType.media_user,
                provider=login_data.provider,
                provider_user_id=provider_user_id,
                server_id=server.id,
                username=login_data.username,
                email=user_email
            )
            self.db.add(user)
        else:
            # Update existing user info
            user.username = login_data.username
            user.email = user_email

        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_tokens(self, user: User) -> TokenResponse:
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(user.id), "type": user.type.value},
            expires_delta=access_token_expires
        )

        # Create refresh token
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "type": user.type.value}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            must_change_password=getattr(user, 'must_change_password', False)
        )

    async def create_initial_admin(self) -> User:
        """Create the initial admin user if it doesn't exist"""
        existing_admin = self.db.query(User).filter(
            User.type == UserType.admin
        ).first()

        if existing_admin:
            return existing_admin

        admin_user = User(
            type=UserType.admin,
            username=settings.admin_username,
            password_hash=get_password_hash(settings.admin_password),
            must_change_password=True
        )

        self.db.add(admin_user)
        self.db.commit()
        self.db.refresh(admin_user)
        return admin_user