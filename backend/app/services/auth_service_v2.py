"""
Enhanced Authentication Service
Handles all authentication-related database operations
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from ..models.user import User, UserType
from ..models.server import Server, ServerType
from ..core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class AuthServiceV2:
    """Enhanced authentication service that handles all DB operations for auth"""

    def __init__(self, db: Session):
        self.db = db

    def get_server_by_uri(self, uri: str, server_type: ServerType) -> Optional[Server]:
        """Find a server by its URI and type"""
        return self.db.query(Server).filter(
            Server.type == server_type,
            Server.enabled == True,
            Server.base_url.contains(uri.replace("https://", "").replace("http://", ""))
        ).first()

    def get_or_create_plex_user(
        self,
        provider_user_id: str,
        server_id: int,
        username: str,
        email: Optional[str] = None,
        thumb: Optional[str] = None,
        home: bool = False
    ) -> User:
        """Get or create a Plex user"""
        user = self.db.query(User).filter(
            User.provider_user_id == str(provider_user_id),
            User.server_id == server_id,
            User.type == UserType.media_user
        ).first()

        if not user:
            user = User(
                username=username,
                email=email,
                provider_user_id=str(provider_user_id),
                server_id=server_id,
                type=UserType.media_user,
                thumb_url=thumb,
                is_home_user=home,
                is_active=True,
                provider="plex"
            )
            self.db.add(user)
        else:
            # Update user info
            user.username = username
            user.email = email
            user.thumb_url = thumb
            user.is_home_user = home
            user.last_login = datetime.utcnow()

        self.db.commit()
        self.db.refresh(user)
        return user

    def get_server_by_id(self, server_id: int, server_type: ServerType) -> Optional[Server]:
        """Get a server by ID and type"""
        return self.db.query(Server).filter(
            Server.id == server_id,
            Server.type == server_type,
            Server.enabled == True
        ).first()

    def get_all_servers_by_type(self, server_type: ServerType) -> List[Server]:
        """Get all enabled servers of a specific type"""
        return self.db.query(Server).filter(
            Server.type == server_type,
            Server.enabled == True
        ).all()

    def get_or_create_media_user(
        self,
        provider_user_id: str,
        server_id: int,
        username: str,
        email: Optional[str] = None,
        provider: str = "emby"
    ) -> User:
        """Get or create an Emby/Jellyfin user"""
        user = self.db.query(User).filter(
            User.provider_user_id == provider_user_id,
            User.server_id == server_id,
            User.type == UserType.media_user
        ).first()

        if not user:
            user = User(
                username=username,
                email=email,
                provider_user_id=provider_user_id,
                server_id=server_id,
                type=UserType.media_user,
                is_active=True,
                provider=provider
            )
            self.db.add(user)
        else:
            # Update user info
            user.username = username
            user.email = email
            user.last_login = datetime.utcnow()

        self.db.commit()
        self.db.refresh(user)
        return user

    def get_all_enabled_media_servers(self) -> List[Server]:
        """Get all enabled media servers (Plex, Emby, Jellyfin)"""
        return self.db.query(Server).filter(
            Server.enabled == True,
            Server.type.in_([ServerType.plex, ServerType.emby, ServerType.jellyfin])
        ).all()

    def find_user_by_credentials(self, username: str, password_hash: Optional[str] = None) -> Optional[User]:
        """Find a user by username and optionally verify password"""
        user = self.db.query(User).filter(
            User.username == username,
            User.type.in_([UserType.admin, UserType.local_user])
        ).first()

        if user and password_hash:
            if not verify_password(password_hash, user.hashed_password):
                return None

        return user

    def update_user_last_login(self, user: User) -> None:
        """Update user's last login timestamp"""
        user.last_login = datetime.utcnow()
        self.db.commit()

    def create_media_user_from_provider(
        self,
        provider_data: Dict[str, Any],
        server: Server,
        provider: str
    ) -> User:
        """Create a media user from provider data"""
        user = User(
            username=provider_data.get("username", provider_data.get("name", "Unknown")),
            email=provider_data.get("email"),
            provider_user_id=str(provider_data.get("id", "")),
            server_id=server.id,
            type=UserType.media_user,
            is_active=True,
            provider=provider,
            thumb_url=provider_data.get("thumb")
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user