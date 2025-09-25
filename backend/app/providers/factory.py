from typing import Dict, Any
from ..models.server import Server, ServerType
from ..services.server_service import ServerService
from .base import BaseProvider
from .plex import PlexProvider
from .emby import EmbyProvider
from .jellyfin import JellyfinProvider


class ProviderFactory:
    @staticmethod
    def create_provider(server: Server, db_session=None) -> BaseProvider:
        """Create a provider instance for the given server"""

        # Get credentials for the server
        if db_session:
            server_service = ServerService(db_session)
            credentials = server_service.get_server_credentials(server.id)
        else:
            # Fallback - credentials should be provided separately
            credentials = {}

        if server.type == ServerType.plex:
            return PlexProvider(server, credentials)
        elif server.type == ServerType.emby:
            return EmbyProvider(server, credentials)
        elif server.type == ServerType.jellyfin:
            return JellyfinProvider(server, credentials)
        else:
            raise ValueError(f"Unsupported server type: {server.type}")

    @staticmethod
    def get_supported_types() -> list:
        """Get list of supported provider types"""
        return [ServerType.plex, ServerType.emby, ServerType.jellyfin]