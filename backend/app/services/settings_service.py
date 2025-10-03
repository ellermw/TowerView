"""
Settings Service
Handles all settings-related database operations
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..models.settings import SystemSettings, NetdataIntegration, PortainerIntegration
from ..models.user import User

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing system and integration settings"""

    def __init__(self, db: Session):
        self.db = db

    # Site Settings
    def get_site_name(self) -> str:
        """Get the site name setting"""
        setting = self.db.query(SystemSettings).filter_by(key="site_name").first()
        return setting.value if setting else "The Tower - View"

    def update_site_name(self, site_name: str, user_id: int) -> None:
        """Update the site name setting"""
        setting = self.db.query(SystemSettings).filter_by(key="site_name").first()

        if not setting:
            setting = SystemSettings(
                key="site_name",
                value=site_name,
                category="general",
                description="The display name of the application",
                updated_by_id=user_id
            )
            self.db.add(setting)
        else:
            setting.value = site_name
            setting.updated_by_id = user_id

        self.db.commit()

    # Sync Settings
    def get_sync_settings(self) -> Dict[str, Any]:
        """Get all sync-related settings"""
        defaults = {
            "user_sync_enabled": False,
            "user_sync_interval_seconds": 3600,
            "library_sync_enabled": False,
            "library_sync_interval_seconds": 86400,
            "library_passive_discovery": True,
            "sessions_cache_interval_seconds": 30,
            "analytics_cache_interval_seconds": 300,
            "server_status_interval_seconds": 60,
        }

        settings_keys = list(defaults.keys()) + ["user_sync_last_run", "library_sync_last_run"]
        settings_db = self.db.query(SystemSettings).filter(
            SystemSettings.key.in_(settings_keys)
        ).all()

        settings_dict = {s.key: s.value for s in settings_db}

        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in settings_dict:
                settings_dict[key] = default_value

        return settings_dict

    def update_sync_setting(self, key: str, value: Any, user_id: int, category: str = "sync") -> None:
        """Update or create a sync setting"""
        setting = self.db.query(SystemSettings).filter_by(key=key).first()

        if not setting:
            setting = SystemSettings(
                key=key,
                value=value,
                category=category,
                description=f"Sync setting: {key}",
                updated_by_id=user_id
            )
            self.db.add(setting)
        else:
            setting.value = value
            setting.updated_by_id = user_id

        self.db.commit()

    def update_sync_settings_batch(self, settings: Dict[str, Any], user_id: int) -> None:
        """Update multiple sync settings at once"""
        for key, value in settings.items():
            self.update_sync_setting(key, value, user_id)

    # Netdata Integration
    def get_netdata_integration(self, user_id: int) -> Optional[NetdataIntegration]:
        """Get Netdata integration for a user"""
        return self.db.query(NetdataIntegration).filter_by(created_by_id=user_id).first()

    def create_netdata_integration(
        self,
        user_id: int,
        api_token: str,
        space_id: str,
        enabled: bool = True
    ) -> NetdataIntegration:
        """Create or update Netdata integration"""
        integration = self.get_netdata_integration(user_id)

        if not integration:
            integration = NetdataIntegration(
                created_by_id=user_id,
                api_token=api_token,
                space_id=space_id,
                enabled=enabled
            )
            self.db.add(integration)
        else:
            integration.api_token = api_token
            integration.space_id = space_id
            integration.enabled = enabled

        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update_netdata_node_mapping(
        self,
        user_id: int,
        server_id: int,
        node_id: str,
        node_name: str,
        container_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update Netdata node mapping for a server"""
        integration = self.get_netdata_integration(user_id)

        if not integration:
            raise ValueError("Netdata integration not configured")

        if not integration.node_mappings:
            integration.node_mappings = {}

        mappings = dict(integration.node_mappings)
        mappings[str(server_id)] = {
            "node_id": node_id,
            "node_name": node_name,
            "container_name": container_name
        }
        integration.node_mappings = mappings

        self.db.commit()
        return mappings

    def delete_netdata_node_mapping(self, user_id: int, server_id: int) -> bool:
        """Delete a Netdata node mapping"""
        integration = self.get_netdata_integration(user_id)

        if not integration or not integration.node_mappings:
            return False

        mappings = dict(integration.node_mappings)
        if str(server_id) in mappings:
            del mappings[str(server_id)]
            integration.node_mappings = mappings
            self.db.commit()
            return True

        return False

    def update_netdata_cache(
        self,
        user_id: int,
        nodes: List[Dict[str, Any]]
    ) -> None:
        """Update cached Netdata nodes"""
        integration = self.get_netdata_integration(user_id)

        if integration:
            integration.cached_nodes = nodes
            integration.nodes_updated_at = datetime.utcnow()
            self.db.commit()

    def delete_netdata_integration(self, user_id: int) -> bool:
        """Delete Netdata integration"""
        integration = self.get_netdata_integration(user_id)

        if integration:
            self.db.delete(integration)
            self.db.commit()
            return True

        return False

    # Portainer Integration
    def get_portainer_integration(self, enabled_only: bool = True) -> Optional[PortainerIntegration]:
        """Get Portainer integration (global, not user-specific)"""
        query = self.db.query(PortainerIntegration)
        if enabled_only:
            query = query.filter_by(enabled=True)
        return query.first()

    def create_portainer_integration(
        self,
        user_id: int,
        url: str,
        api_token: str,
        endpoint_id: int = 1
    ) -> PortainerIntegration:
        """Create or update Portainer integration"""
        integration = self.get_portainer_integration(enabled_only=False)

        if not integration:
            integration = PortainerIntegration(
                created_by_id=user_id,
                url=url,
                api_token=api_token,
                endpoint_id=endpoint_id,
                enabled=True
            )
            self.db.add(integration)
        else:
            integration.url = url
            integration.api_token = api_token
            integration.endpoint_id = endpoint_id
            integration.enabled = True
            integration.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update_portainer_container_mapping(
        self,
        server_id: int,
        container_id: str,
        container_name: str
    ) -> Dict[str, Any]:
        """Update Portainer container mapping for a server"""
        integration = self.get_portainer_integration()

        if not integration:
            raise ValueError("Portainer integration not configured")

        if not integration.container_mappings:
            integration.container_mappings = {}

        mappings = dict(integration.container_mappings)
        mappings[str(server_id)] = {
            "container_id": container_id,
            "container_name": container_name
        }
        integration.container_mappings = mappings

        self.db.commit()
        return mappings

    def update_portainer_cache(
        self,
        containers: List[Dict[str, Any]]
    ) -> None:
        """Update cached Portainer containers"""
        integration = self.get_portainer_integration()

        if integration:
            integration.cached_containers = containers
            integration.containers_updated_at = datetime.utcnow()
            self.db.commit()

    def update_portainer_container_id(
        self,
        server_id: int,
        new_container_id: str
    ) -> None:
        """Update container ID in Portainer mapping (after recreate)"""
        integration = self.get_portainer_integration()

        if integration and integration.container_mappings:
            mappings = dict(integration.container_mappings)
            if str(server_id) in mappings:
                mappings[str(server_id)]["container_id"] = new_container_id[:12]
                integration.container_mappings = mappings
                self.db.commit()

    def delete_portainer_integration(self) -> bool:
        """Delete Portainer integration"""
        integration = self.get_portainer_integration(enabled_only=False)

        if integration:
            self.db.delete(integration)
            self.db.commit()
            return True

        return False