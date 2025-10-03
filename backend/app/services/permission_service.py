"""
Permission Service
Handles all permission-related database operations
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from ..models.user import User, UserType
from ..models.user_permission import UserPermission
from ..models.server import Server

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing user permissions"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_server_permission(
        self,
        user_id: int,
        server_id: int
    ) -> Optional[UserPermission]:
        """Get permission for a user on a specific server"""
        return self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.server_id == server_id
        ).first()

    def get_user_permissions(self, user_id: int) -> List[UserPermission]:
        """Get all permissions for a user"""
        return self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id
        ).all()

    def get_user_permitted_servers(
        self,
        user_id: int,
        can_view: bool = True,
        can_manage: bool = False
    ) -> List[int]:
        """Get list of server IDs that user has permission for"""
        query = self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id
        )

        if can_view:
            query = query.filter(UserPermission.can_view_servers == True)
        if can_manage:
            query = query.filter(UserPermission.can_manage_servers == True)

        permissions = query.all()
        return [p.server_id for p in permissions]

    def check_server_access(
        self,
        user: User,
        server_id: int,
        require_manage: bool = False
    ) -> bool:
        """Check if user has access to a server"""
        # Admin users check ownership
        if user.type in [UserType.admin, UserType.staff, UserType.support]:
            server = self.db.query(Server).filter(Server.id == server_id).first()
            return server and server.owner_id == user.id

        # Local users check permissions
        permission = self.get_user_server_permission(user.id, server_id)
        if not permission:
            return False

        if require_manage:
            return permission.can_manage_servers or permission.can_manage_server
        else:
            return permission.can_view_servers

    def create_or_update_permission(
        self,
        user_id: int,
        server_id: int,
        can_view_servers: bool = False,
        can_manage_servers: bool = False,
        can_view_all_sessions: bool = False,
        can_terminate_sessions: bool = False,
        can_manage_server: bool = False
    ) -> UserPermission:
        """Create or update a user permission"""
        permission = self.get_user_server_permission(user_id, server_id)

        if not permission:
            permission = UserPermission(
                user_id=user_id,
                server_id=server_id,
                can_view_servers=can_view_servers,
                can_manage_servers=can_manage_servers,
                can_view_all_sessions=can_view_all_sessions,
                can_terminate_sessions=can_terminate_sessions,
                can_manage_server=can_manage_server
            )
            self.db.add(permission)
        else:
            permission.can_view_servers = can_view_servers
            permission.can_manage_servers = can_manage_servers
            permission.can_view_all_sessions = can_view_all_sessions
            permission.can_terminate_sessions = can_terminate_sessions
            permission.can_manage_server = can_manage_server

        self.db.commit()
        self.db.refresh(permission)
        return permission

    def delete_permission(self, user_id: int, server_id: int) -> bool:
        """Delete a user permission"""
        permission = self.get_user_server_permission(user_id, server_id)
        if permission:
            self.db.delete(permission)
            self.db.commit()
            return True
        return False

    def delete_all_user_permissions(self, user_id: int) -> int:
        """Delete all permissions for a user"""
        count = self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id
        ).delete()
        self.db.commit()
        return count

    def get_server_permissions(self, server_id: int) -> List[UserPermission]:
        """Get all permissions for a specific server"""
        return self.db.query(UserPermission).filter(
            UserPermission.server_id == server_id
        ).all()

    def check_analytics_access(self, user: User) -> Optional[List[int]]:
        """Check if user has access to analytics and return allowed server IDs"""
        if user.type == UserType.admin:
            return None  # Admin has access to all their servers

        if user.type == UserType.local_user:
            allowed_server_ids = self.get_user_permitted_servers(user.id, can_view=True)
            return allowed_server_ids if allowed_server_ids else []

        return []  # Other user types don't have analytics access

    def check_library_management_access(
        self,
        user: User,
        server_id: int
    ) -> bool:
        """Check if user can manage libraries on a server"""
        if user.type == UserType.admin:
            server = self.db.query(Server).filter(Server.id == server_id).first()
            return server and server.owner_id == user.id

        if user.type == UserType.local_user:
            permission = self.get_user_server_permission(user.id, server_id)
            return permission and permission.can_manage_servers

        return False

    def check_session_termination_access(
        self,
        user: User,
        server_id: int,
        session_username: Optional[str] = None
    ) -> bool:
        """Check if user can terminate sessions on a server"""
        # Admin/staff can terminate if they own the server
        if user.type in [UserType.admin, UserType.staff, UserType.support]:
            server = self.db.query(Server).filter(Server.id == server_id).first()
            return server and server.owner_id == user.id

        # Local users need specific permission
        if user.type == UserType.local_user:
            permission = self.get_user_server_permission(user.id, server_id)
            return permission and permission.can_manage_servers

        # Media users can only terminate their own sessions
        if user.type == UserType.media_user:
            if session_username and session_username.lower() == user.username.lower():
                permission = self.get_user_server_permission(user.id, server_id)
                return permission and permission.can_manage_server
            return False

        return False