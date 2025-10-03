"""
Tests for Permission Service
"""
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.services.permission_service import PermissionService
from app.models.user import User, UserType
from app.models.user_permission import UserPermission
from app.models.server import Server


@pytest.fixture
def db_session():
    """Create a mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def permission_service(db_session):
    """Create a PermissionService instance with mocked database"""
    return PermissionService(db_session)


class TestPermissionService:
    """Test cases for PermissionService"""

    def test_get_user_server_permission(self, permission_service, db_session):
        """Test getting permission for user on specific server"""
        mock_permission = UserPermission(
            user_id=1,
            server_id=10,
            can_view_servers=True
        )
        db_session.query().filter().first.return_value = mock_permission

        result = permission_service.get_user_server_permission(1, 10)

        assert result == mock_permission
        assert result.can_view_servers == True

    def test_get_user_permissions(self, permission_service, db_session):
        """Test getting all permissions for a user"""
        mock_permissions = [
            UserPermission(user_id=1, server_id=10),
            UserPermission(user_id=1, server_id=20)
        ]
        db_session.query().filter().all.return_value = mock_permissions

        result = permission_service.get_user_permissions(1)

        assert len(result) == 2
        assert all(p.user_id == 1 for p in result)

    def test_get_user_permitted_servers_view_only(self, permission_service, db_session):
        """Test getting servers user can view"""
        mock_permissions = [
            UserPermission(user_id=1, server_id=10, can_view_servers=True),
            UserPermission(user_id=1, server_id=20, can_view_servers=True),
            UserPermission(user_id=1, server_id=30, can_view_servers=False)
        ]
        # Mock the filter chain
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_permissions[0], mock_permissions[1]]

        result = permission_service.get_user_permitted_servers(1, can_view=True)

        assert result == [10, 20]

    def test_get_user_permitted_servers_manage(self, permission_service, db_session):
        """Test getting servers user can manage"""
        mock_permissions = [
            UserPermission(user_id=1, server_id=10, can_manage_servers=True),
        ]
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_permissions

        result = permission_service.get_user_permitted_servers(1, can_manage=True)

        assert result == [10]

    def test_check_server_access_admin_owner(self, permission_service, db_session):
        """Test admin access to owned server"""
        mock_user = User(id=1, type=UserType.admin)
        mock_server = Server(id=10, owner_id=1)

        db_session.query().filter().first.return_value = mock_server

        result = permission_service.check_server_access(mock_user, 10)

        assert result == True

    def test_check_server_access_admin_not_owner(self, permission_service, db_session):
        """Test admin access to non-owned server"""
        mock_user = User(id=1, type=UserType.admin)
        mock_server = Server(id=10, owner_id=2)  # Different owner

        db_session.query().filter().first.return_value = mock_server

        result = permission_service.check_server_access(mock_user, 10)

        assert result == False

    def test_check_server_access_local_user_with_permission(self, permission_service, db_session):
        """Test local user with permission to access server"""
        mock_user = User(id=2, type=UserType.local_user)
        mock_permission = UserPermission(
            user_id=2,
            server_id=10,
            can_view_servers=True
        )

        # Mock the permission query
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_permission

        result = permission_service.check_server_access(mock_user, 10)

        assert result == True

    def test_check_server_access_local_user_no_permission(self, permission_service, db_session):
        """Test local user without permission"""
        mock_user = User(id=2, type=UserType.local_user)

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = permission_service.check_server_access(mock_user, 10)

        assert result == False

    def test_check_server_access_require_manage(self, permission_service, db_session):
        """Test checking for manage permission"""
        mock_user = User(id=2, type=UserType.local_user)
        mock_permission = UserPermission(
            user_id=2,
            server_id=10,
            can_view_servers=True,
            can_manage_servers=True
        )

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_permission

        result = permission_service.check_server_access(mock_user, 10, require_manage=True)

        assert result == True

    def test_create_or_update_permission_new(self, permission_service, db_session):
        """Test creating new permission"""
        # No existing permission
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = permission_service.create_or_update_permission(
            user_id=3,
            server_id=30,
            can_view_servers=True,
            can_manage_servers=False
        )

        db_session.add.assert_called_once()
        added_permission = db_session.add.call_args[0][0]
        assert added_permission.user_id == 3
        assert added_permission.server_id == 30
        assert added_permission.can_view_servers == True
        assert added_permission.can_manage_servers == False
        db_session.commit.assert_called_once()

    def test_create_or_update_permission_existing(self, permission_service, db_session):
        """Test updating existing permission"""
        existing_permission = UserPermission(
            user_id=3,
            server_id=30,
            can_view_servers=False
        )

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = existing_permission

        result = permission_service.create_or_update_permission(
            user_id=3,
            server_id=30,
            can_view_servers=True,
            can_manage_servers=True
        )

        assert existing_permission.can_view_servers == True
        assert existing_permission.can_manage_servers == True
        db_session.commit.assert_called_once()

    def test_delete_permission(self, permission_service, db_session):
        """Test deleting a permission"""
        mock_permission = UserPermission(user_id=4, server_id=40)

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_permission

        result = permission_service.delete_permission(4, 40)

        assert result == True
        db_session.delete.assert_called_once_with(mock_permission)
        db_session.commit.assert_called_once()

    def test_delete_permission_not_found(self, permission_service, db_session):
        """Test deleting non-existent permission"""
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = permission_service.delete_permission(4, 40)

        assert result == False
        db_session.delete.assert_not_called()

    def test_delete_all_user_permissions(self, permission_service, db_session):
        """Test deleting all permissions for a user"""
        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 3  # Deleted 3 permissions

        result = permission_service.delete_all_user_permissions(5)

        assert result == 3
        db_session.commit.assert_called_once()

    def test_check_analytics_access_admin(self, permission_service, db_session):
        """Test admin analytics access"""
        mock_user = User(id=1, type=UserType.admin)

        result = permission_service.check_analytics_access(mock_user)

        assert result is None  # Admin has access to all

    def test_check_analytics_access_local_user(self, permission_service, db_session):
        """Test local user analytics access"""
        mock_user = User(id=2, type=UserType.local_user)
        mock_permissions = [
            UserPermission(user_id=2, server_id=10, can_view_servers=True),
            UserPermission(user_id=2, server_id=20, can_view_servers=True)
        ]

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_permissions

        result = permission_service.check_analytics_access(mock_user)

        assert result == [10, 20]

    def test_check_library_management_access_admin(self, permission_service, db_session):
        """Test admin library management access"""
        mock_user = User(id=1, type=UserType.admin)
        mock_server = Server(id=10, owner_id=1)

        db_session.query().filter().first.return_value = mock_server

        result = permission_service.check_library_management_access(mock_user, 10)

        assert result == True

    def test_check_session_termination_access_media_user_own_session(self, permission_service, db_session):
        """Test media user terminating own session"""
        mock_user = User(id=3, type=UserType.media_user, username="mediauser")
        mock_permission = UserPermission(
            user_id=3,
            server_id=10,
            can_manage_server=True
        )

        mock_query = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_permission

        result = permission_service.check_session_termination_access(
            mock_user, 10, session_username="MediaUser"
        )

        assert result == True

    def test_check_session_termination_access_media_user_other_session(self, permission_service, db_session):
        """Test media user trying to terminate another user's session"""
        mock_user = User(id=3, type=UserType.media_user, username="mediauser")

        result = permission_service.check_session_termination_access(
            mock_user, 10, session_username="OtherUser"
        )

        assert result == False