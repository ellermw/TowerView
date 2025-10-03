"""
Tests for Enhanced Authentication Service
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.auth_service_v2 import AuthServiceV2
from app.models.user import User, UserType
from app.models.server import Server, ServerType


@pytest.fixture
def db_session():
    """Create a mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def auth_service(db_session):
    """Create an AuthServiceV2 instance with mocked database"""
    return AuthServiceV2(db_session)


class TestAuthServiceV2:
    """Test cases for AuthServiceV2"""

    def test_get_server_by_uri(self, auth_service, db_session):
        """Test finding a server by URI"""
        # Setup mock
        mock_server = Server(
            id=1,
            base_url="plex.example.com",
            type=ServerType.plex,
            enabled=True
        )
        db_session.query().filter().first.return_value = mock_server

        # Test
        result = auth_service.get_server_by_uri("https://plex.example.com", ServerType.plex)

        # Assert
        assert result == mock_server
        db_session.query.assert_called_once()

    def test_get_server_by_uri_not_found(self, auth_service, db_session):
        """Test server not found by URI"""
        db_session.query().filter().first.return_value = None

        result = auth_service.get_server_by_uri("nonexistent.com", ServerType.plex)

        assert result is None

    def test_get_or_create_plex_user_existing(self, auth_service, db_session):
        """Test getting an existing Plex user"""
        # Setup mock existing user
        existing_user = User(
            id=1,
            username="testuser",
            provider_user_id="123",
            server_id=1,
            type=UserType.media_user
        )
        db_session.query().filter().first.return_value = existing_user

        # Test
        result = auth_service.get_or_create_plex_user(
            provider_user_id="123",
            server_id=1,
            username="testuser",
            email="test@example.com"
        )

        # Assert
        assert result == existing_user
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        db_session.commit.assert_called_once()
        db_session.refresh.assert_called_once_with(existing_user)

    def test_get_or_create_plex_user_new(self, auth_service, db_session):
        """Test creating a new Plex user"""
        # Setup mock - no existing user
        db_session.query().filter().first.return_value = None

        # Test
        result = auth_service.get_or_create_plex_user(
            provider_user_id="456",
            server_id=2,
            username="newuser",
            email="new@example.com",
            thumb="thumb_url",
            home=True
        )

        # Assert
        db_session.add.assert_called_once()
        added_user = db_session.add.call_args[0][0]
        assert added_user.username == "newuser"
        assert added_user.email == "new@example.com"
        assert added_user.provider_user_id == "456"
        assert added_user.server_id == 2
        assert added_user.is_home_user == True
        assert added_user.provider == "plex"
        db_session.commit.assert_called_once()

    def test_get_all_servers_by_type(self, auth_service, db_session):
        """Test getting all servers of a specific type"""
        # Setup mock servers
        mock_servers = [
            Server(id=1, type=ServerType.plex, enabled=True),
            Server(id=2, type=ServerType.plex, enabled=True)
        ]
        db_session.query().filter().all.return_value = mock_servers

        # Test
        result = auth_service.get_all_servers_by_type(ServerType.plex)

        # Assert
        assert result == mock_servers
        assert len(result) == 2

    def test_get_or_create_media_user_existing(self, auth_service, db_session):
        """Test getting an existing Emby/Jellyfin user"""
        existing_user = User(
            id=1,
            username="embyuser",
            provider_user_id="789",
            server_id=3,
            type=UserType.media_user
        )
        db_session.query().filter().first.return_value = existing_user

        result = auth_service.get_or_create_media_user(
            provider_user_id="789",
            server_id=3,
            username="embyuser",
            email="emby@example.com",
            provider="emby"
        )

        assert result == existing_user
        assert result.email == "emby@example.com"
        db_session.commit.assert_called_once()

    def test_get_or_create_media_user_new(self, auth_service, db_session):
        """Test creating a new Emby/Jellyfin user"""
        db_session.query().filter().first.return_value = None

        result = auth_service.get_or_create_media_user(
            provider_user_id="101",
            server_id=4,
            username="jellyuser",
            email="jelly@example.com",
            provider="jellyfin"
        )

        db_session.add.assert_called_once()
        added_user = db_session.add.call_args[0][0]
        assert added_user.username == "jellyuser"
        assert added_user.provider == "jellyfin"
        assert added_user.provider_user_id == "101"

    def test_find_user_by_credentials_valid(self, auth_service, db_session):
        """Test finding user with valid credentials"""
        mock_user = User(
            username="admin",
            type=UserType.admin,
            hashed_password="hashed_pwd"
        )
        db_session.query().filter().first.return_value = mock_user

        with patch('app.services.auth_service_v2.verify_password', return_value=True):
            result = auth_service.find_user_by_credentials("admin", "password123")

        assert result == mock_user

    def test_find_user_by_credentials_invalid_password(self, auth_service, db_session):
        """Test finding user with invalid password"""
        mock_user = User(
            username="admin",
            type=UserType.admin,
            hashed_password="hashed_pwd"
        )
        db_session.query().filter().first.return_value = mock_user

        with patch('app.services.auth_service_v2.verify_password', return_value=False):
            result = auth_service.find_user_by_credentials("admin", "wrongpassword")

        assert result is None

    def test_update_user_last_login(self, auth_service, db_session):
        """Test updating user's last login timestamp"""
        mock_user = User(username="testuser")

        auth_service.update_user_last_login(mock_user)

        assert mock_user.last_login is not None
        assert isinstance(mock_user.last_login, datetime)
        db_session.commit.assert_called_once()

    def test_create_media_user_from_provider(self, auth_service, db_session):
        """Test creating media user from provider data"""
        mock_server = Server(id=5)
        provider_data = {
            "id": "provider123",
            "username": "provideruser",
            "email": "provider@example.com",
            "thumb": "thumb_url"
        }

        result = auth_service.create_media_user_from_provider(
            provider_data,
            mock_server,
            "plex"
        )

        db_session.add.assert_called_once()
        added_user = db_session.add.call_args[0][0]
        assert added_user.username == "provideruser"
        assert added_user.email == "provider@example.com"
        assert added_user.provider_user_id == "provider123"
        assert added_user.server_id == 5
        assert added_user.provider == "plex"
        db_session.commit.assert_called_once()

    def test_get_all_enabled_media_servers(self, auth_service, db_session):
        """Test getting all enabled media servers"""
        mock_servers = [
            Server(id=1, type=ServerType.plex, enabled=True),
            Server(id=2, type=ServerType.emby, enabled=True),
            Server(id=3, type=ServerType.jellyfin, enabled=True)
        ]
        db_session.query().filter().all.return_value = mock_servers

        result = auth_service.get_all_enabled_media_servers()

        assert len(result) == 3
        assert all(s.enabled for s in result)