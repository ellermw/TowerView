"""
Tests for Settings Service
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.settings_service import SettingsService
from app.models.settings import SystemSettings, NetdataIntegration, PortainerIntegration


@pytest.fixture
def db_session():
    """Create a mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def settings_service(db_session):
    """Create a SettingsService instance with mocked database"""
    return SettingsService(db_session)


class TestSettingsService:
    """Test cases for SettingsService"""

    def test_get_site_name_exists(self, settings_service, db_session):
        """Test getting existing site name"""
        mock_setting = SystemSettings(key="site_name", value="My Custom Site")
        db_session.query().filter_by().first.return_value = mock_setting

        result = settings_service.get_site_name()

        assert result == "My Custom Site"

    def test_get_site_name_default(self, settings_service, db_session):
        """Test getting default site name when not set"""
        db_session.query().filter_by().first.return_value = None

        result = settings_service.get_site_name()

        assert result == "The Tower - View"

    def test_update_site_name_new(self, settings_service, db_session):
        """Test creating new site name setting"""
        db_session.query().filter_by().first.return_value = None

        settings_service.update_site_name("New Site Name", user_id=1)

        db_session.add.assert_called_once()
        added_setting = db_session.add.call_args[0][0]
        assert added_setting.key == "site_name"
        assert added_setting.value == "New Site Name"
        assert added_setting.updated_by_id == 1
        db_session.commit.assert_called_once()

    def test_update_site_name_existing(self, settings_service, db_session):
        """Test updating existing site name"""
        existing_setting = SystemSettings(
            key="site_name",
            value="Old Name",
            updated_by_id=2
        )
        db_session.query().filter_by().first.return_value = existing_setting

        settings_service.update_site_name("Updated Name", user_id=3)

        assert existing_setting.value == "Updated Name"
        assert existing_setting.updated_by_id == 3
        db_session.commit.assert_called_once()

    def test_get_sync_settings(self, settings_service, db_session):
        """Test getting sync settings with defaults"""
        mock_settings = [
            SystemSettings(key="user_sync_enabled", value=True),
            SystemSettings(key="user_sync_interval_seconds", value=7200)
        ]
        db_session.query().filter().all.return_value = mock_settings

        result = settings_service.get_sync_settings()

        assert result["user_sync_enabled"] == True
        assert result["user_sync_interval_seconds"] == 7200
        # Check defaults are applied
        assert result["library_sync_enabled"] == False
        assert result["sessions_cache_interval_seconds"] == 30

    def test_update_sync_setting_new(self, settings_service, db_session):
        """Test creating new sync setting"""
        db_session.query().filter_by().first.return_value = None

        settings_service.update_sync_setting("test_setting", "test_value", user_id=1)

        db_session.add.assert_called_once()
        added_setting = db_session.add.call_args[0][0]
        assert added_setting.key == "test_setting"
        assert added_setting.value == "test_value"
        assert added_setting.category == "sync"
        db_session.commit.assert_called_once()

    def test_update_sync_settings_batch(self, settings_service, db_session):
        """Test updating multiple sync settings"""
        settings = {
            "setting1": "value1",
            "setting2": "value2"
        }

        # Mock query returning None for new settings
        db_session.query().filter_by().first.return_value = None

        settings_service.update_sync_settings_batch(settings, user_id=1)

        # Should be called twice (once for each setting)
        assert db_session.add.call_count == 2
        assert db_session.commit.call_count == 2

    def test_get_netdata_integration(self, settings_service, db_session):
        """Test getting Netdata integration"""
        mock_integration = NetdataIntegration(
            created_by_id=1,
            api_token="token123",
            space_id="space123",
            enabled=True
        )
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.get_netdata_integration(1)

        assert result == mock_integration
        assert result.api_token == "token123"

    def test_create_netdata_integration_new(self, settings_service, db_session):
        """Test creating new Netdata integration"""
        db_session.query().filter_by().first.return_value = None

        result = settings_service.create_netdata_integration(
            user_id=1,
            api_token="new_token",
            space_id="new_space",
            enabled=True
        )

        db_session.add.assert_called_once()
        added_integration = db_session.add.call_args[0][0]
        assert added_integration.api_token == "new_token"
        assert added_integration.space_id == "new_space"
        assert added_integration.enabled == True
        db_session.commit.assert_called_once()

    def test_create_netdata_integration_update(self, settings_service, db_session):
        """Test updating existing Netdata integration"""
        existing_integration = NetdataIntegration(
            created_by_id=1,
            api_token="old_token",
            space_id="old_space",
            enabled=False
        )
        db_session.query().filter_by().first.return_value = existing_integration

        result = settings_service.create_netdata_integration(
            user_id=1,
            api_token="updated_token",
            space_id="updated_space",
            enabled=True
        )

        assert existing_integration.api_token == "updated_token"
        assert existing_integration.space_id == "updated_space"
        assert existing_integration.enabled == True
        db_session.commit.assert_called_once()

    def test_update_netdata_node_mapping(self, settings_service, db_session):
        """Test updating Netdata node mapping"""
        mock_integration = NetdataIntegration(
            created_by_id=1,
            node_mappings={"1": {"node_id": "old_node"}}
        )
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.update_netdata_node_mapping(
            user_id=1,
            server_id=2,
            node_id="node123",
            node_name="Node 123",
            container_name="container1"
        )

        assert "2" in result
        assert result["2"]["node_id"] == "node123"
        assert result["2"]["node_name"] == "Node 123"
        assert result["2"]["container_name"] == "container1"
        db_session.commit.assert_called_once()

    def test_update_netdata_node_mapping_no_integration(self, settings_service, db_session):
        """Test updating node mapping without integration"""
        db_session.query().filter_by().first.return_value = None

        with pytest.raises(ValueError, match="Netdata integration not configured"):
            settings_service.update_netdata_node_mapping(
                user_id=1,
                server_id=1,
                node_id="node123",
                node_name="Node"
            )

    def test_delete_netdata_node_mapping(self, settings_service, db_session):
        """Test deleting Netdata node mapping"""
        mock_integration = NetdataIntegration(
            node_mappings={"1": {"node_id": "node1"}, "2": {"node_id": "node2"}}
        )
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.delete_netdata_node_mapping(1, server_id=1)

        assert result == True
        assert "1" not in mock_integration.node_mappings
        assert "2" in mock_integration.node_mappings
        db_session.commit.assert_called_once()

    def test_update_netdata_cache(self, settings_service, db_session):
        """Test updating Netdata cache"""
        mock_integration = NetdataIntegration()
        db_session.query().filter_by().first.return_value = mock_integration

        nodes = [{"id": "node1"}, {"id": "node2"}]
        settings_service.update_netdata_cache(1, nodes)

        assert mock_integration.cached_nodes == nodes
        assert mock_integration.nodes_updated_at is not None
        db_session.commit.assert_called_once()

    def test_delete_netdata_integration(self, settings_service, db_session):
        """Test deleting Netdata integration"""
        mock_integration = NetdataIntegration()
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.delete_netdata_integration(1)

        assert result == True
        db_session.delete.assert_called_once_with(mock_integration)
        db_session.commit.assert_called_once()

    def test_get_portainer_integration(self, settings_service, db_session):
        """Test getting Portainer integration"""
        mock_integration = PortainerIntegration(
            url="https://portainer.example.com",
            api_token="token456",
            enabled=True
        )
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.get_portainer_integration()

        assert result == mock_integration
        assert result.url == "https://portainer.example.com"

    def test_create_portainer_integration_new(self, settings_service, db_session):
        """Test creating new Portainer integration"""
        db_session.query().filter_by().first.return_value = None

        result = settings_service.create_portainer_integration(
            user_id=1,
            url="https://new.portainer.com",
            api_token="new_token",
            endpoint_id=2
        )

        db_session.add.assert_called_once()
        added_integration = db_session.add.call_args[0][0]
        assert added_integration.url == "https://new.portainer.com"
        assert added_integration.api_token == "new_token"
        assert added_integration.endpoint_id == 2
        assert added_integration.enabled == True
        db_session.commit.assert_called_once()

    def test_update_portainer_container_mapping(self, settings_service, db_session):
        """Test updating Portainer container mapping"""
        mock_integration = PortainerIntegration(
            container_mappings={"1": {"container_id": "old_container"}}
        )
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.update_portainer_container_mapping(
            server_id=2,
            container_id="container123",
            container_name="Container 123"
        )

        assert "2" in result
        assert result["2"]["container_id"] == "container123"
        assert result["2"]["container_name"] == "Container 123"
        db_session.commit.assert_called_once()

    def test_update_portainer_cache(self, settings_service, db_session):
        """Test updating Portainer cache"""
        mock_integration = PortainerIntegration()
        db_session.query().filter_by().first.return_value = mock_integration

        containers = [{"Id": "c1"}, {"Id": "c2"}]
        settings_service.update_portainer_cache(containers)

        assert mock_integration.cached_containers == containers
        assert mock_integration.containers_updated_at is not None
        db_session.commit.assert_called_once()

    def test_update_portainer_container_id(self, settings_service, db_session):
        """Test updating Portainer container ID after recreate"""
        mock_integration = PortainerIntegration(
            container_mappings={
                "1": {"container_id": "old_id", "container_name": "container1"}
            }
        )
        db_session.query().filter_by().first.return_value = mock_integration

        settings_service.update_portainer_container_id(1, "new_container_id")

        assert mock_integration.container_mappings["1"]["container_id"] == "new_container"
        db_session.commit.assert_called_once()

    def test_delete_portainer_integration(self, settings_service, db_session):
        """Test deleting Portainer integration"""
        mock_integration = PortainerIntegration()
        db_session.query().filter_by().first.return_value = mock_integration

        result = settings_service.delete_portainer_integration()

        assert result == True
        db_session.delete.assert_called_once_with(mock_integration)
        db_session.commit.assert_called_once()