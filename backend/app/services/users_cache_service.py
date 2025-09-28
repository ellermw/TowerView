"""
Background service for collecting and caching users from all media servers
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class UsersCacheService:
    """Singleton service that collects users in the background"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.users_cache: List[Dict] = []
            self.last_update: Optional[datetime] = None
            self.last_error: Optional[str] = None
            self.collection_task: Optional[asyncio.Task] = None
            self.is_running = False
            self.update_interval = 60  # Update every 60 seconds (users don't change as often)
            self.cache_ttl = 120  # Cache is valid for 2 minutes
            self._lock = asyncio.Lock()
            self._initialized = True
            logger.info("UsersCacheService initialized")

    async def start(self):
        """Start the background users collection"""
        if self.is_running:
            logger.warning("Users collection already running")
            return

        self.is_running = True
        self.collection_task = asyncio.create_task(self._collect_users_loop())
        logger.info("Started background users collection")

    async def stop(self):
        """Stop the background users collection"""
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background users collection")

    async def get_cached_users(self, user_id: int = None, user_type: str = None, db = None) -> List[Dict]:
        """
        Get cached users filtered by user permissions
        Returns cached data if available and fresh, otherwise triggers a refresh
        """
        # Check if cache is still valid
        if self.last_update and datetime.utcnow() - self.last_update < timedelta(seconds=self.cache_ttl):
            return await self._filter_users_for_user(self.users_cache, user_id, user_type, db)

        # If cache is stale and no background update is running, trigger one
        if not self.collection_task or self.collection_task.done():
            logger.info("Users cache is stale and no update running, triggering refresh")
            await self._collect_all_users()

        # Return whatever we have (even if stale) to avoid blocking
        return await self._filter_users_for_user(self.users_cache, user_id, user_type, db)

    async def _filter_users_for_user(self, users: List[Dict], user_id: int = None, user_type: str = None, db = None) -> List[Dict]:
        """Filter users based on user permissions"""
        if not user_id or not user_type or not db:
            # Admin or no filtering needed
            return users

        if user_type == "admin":
            return users

        # Media users can only see users from servers marked as visible to them
        if user_type == "media_user":
            from ..models.server import Server
            from ..models.user import User

            # Get servers that are visible to media users
            visible_servers = db.query(Server).filter(
                Server.visible_to_media_users == True,
                Server.enabled == True
            ).all()

            visible_server_ids = [server.id for server in visible_servers]

            # Get the current media user's username
            current_user = db.query(User).filter(User.id == user_id).first()
            current_username = current_user.username.lower() if current_user else ""

            # Filter users to only those from visible servers and censor usernames
            filtered_users = []
            for user in users:
                if user.get("server_id") in visible_server_ids:
                    # Make a copy of the user to avoid modifying the cache
                    user_copy = user.copy()

                    # Censor username if it's not the current user
                    username = user_copy.get("username", "")
                    if username and username.lower() != current_username:
                        # Keep first letter, replace rest with asterisks
                        user_copy["username"] = username[0] + "*" * (len(username) - 1)

                    filtered_users.append(user_copy)

            return filtered_users

        # Support users can also see all users (view-only role)
        if user_type == "support":
            return users

        # For staff/local users, filter by permissions
        from ..models.user_permission import UserPermission

        # Get server IDs this user has permission to view users for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.can_view_users == True
        ).all()

        allowed_server_ids = [perm.server_id for perm in permissions]

        # Filter users to only those from allowed servers
        filtered_users = [
            user for user in users
            if user.get("server_id") in allowed_server_ids
        ]

        return filtered_users

    async def _collect_users_loop(self):
        """Main loop that collects users from all servers"""
        # Initial collection
        await self._collect_all_users()

        while self.is_running:
            try:
                await asyncio.sleep(self.update_interval)
                await self._collect_all_users()
            except Exception as e:
                logger.error(f"Error in users collection loop: {e}")
                self.last_error = str(e)
                await asyncio.sleep(self.update_interval * 2)  # Wait longer on error

    async def _collect_all_users(self):
        """Collect users from all configured servers"""
        from ..core.database import SessionLocal
        from ..models.server import Server
        from ..providers.factory import ProviderFactory
        from datetime import datetime

        db = SessionLocal()
        try:
            # Get all active servers
            servers = db.query(Server).filter(Server.enabled == True).all()

            all_users = []
            errors = []

            # Use asyncio.gather to fetch from all servers concurrently
            tasks = []
            for server in servers:
                tasks.append(self._fetch_server_users(server, db))

            # Gather all results
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                    logger.error(f"Error fetching users: {result}")
                elif result:
                    all_users.extend(result)

            # Update cache with lock to ensure thread safety
            async with self._lock:
                self.users_cache = all_users
                self.last_update = datetime.utcnow()
                if errors:
                    self.last_error = f"Errors from {len(errors)} servers: {', '.join(errors[:3])}"
                else:
                    self.last_error = None

            logger.info(f"Cached {len(all_users)} users from {len(servers)} servers")

        except Exception as e:
            logger.error(f"Error collecting users: {e}")
            self.last_error = str(e)
        finally:
            db.close()

    async def _fetch_server_users(self, server, db):
        """Fetch users from a single server"""
        try:
            from ..providers.factory import ProviderFactory

            provider = ProviderFactory.create_provider(server, db)
            users = await provider.list_users()

            # Add server info to each user
            for user in users:
                user["server_name"] = server.name
                user["server_id"] = server.id
                user["server_type"] = server.type.value

            return users

        except Exception as e:
            logger.error(f"Failed to fetch users from server {server.name}: {e}")
            raise

    def get_cache_status(self) -> Dict:
        """Get current cache status"""
        return {
            "is_running": self.is_running,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_error": self.last_error,
            "user_count": len(self.users_cache),
            "cache_age_seconds": (datetime.utcnow() - self.last_update).total_seconds() if self.last_update else None,
            "update_interval": self.update_interval,
            "cache_ttl": self.cache_ttl
        }

# Global instance
users_cache_service = UsersCacheService()