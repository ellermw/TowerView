from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models.server import Server


class BaseProvider(ABC):
    def __init__(self, server: Server, credentials: Dict[str, Any]):
        self.server = server
        self.credentials = credentials
        self.base_url = server.base_url

    @abstractmethod
    async def connect(self) -> bool:
        """Test connection to the server"""
        pass

    @abstractmethod
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with the provider and return user info"""
        pass

    @abstractmethod
    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of currently active sessions"""
        pass

    @abstractmethod
    async def list_users(self) -> List[Dict[str, Any]]:
        """Get list of all users with access to this server"""
        pass

    @abstractmethod
    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information by provider user ID"""
        pass

    @abstractmethod
    async def terminate_session(self, provider_session_id: str) -> bool:
        """Terminate a specific session"""
        pass

    @abstractmethod
    async def modify_user(self, provider_user_id: str, changes: Dict[str, Any]) -> bool:
        """Modify user settings/access"""
        pass

    @abstractmethod
    async def list_libraries(self) -> List[Dict[str, Any]]:
        """Get list of available libraries"""
        pass

    @abstractmethod
    async def set_library_access(self, provider_user_id: str, library_ids: List[str]) -> bool:
        """Set library access for a user"""
        pass

    @abstractmethod
    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get media information by provider media ID"""
        pass