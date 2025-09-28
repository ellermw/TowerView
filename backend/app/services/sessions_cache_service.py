"""
Background service for collecting and caching active sessions from all media servers
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class SessionsCacheService:
    """Singleton service that collects sessions in the background"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.sessions_cache: List[Dict] = []
            self.last_update: Optional[datetime] = None
            self.last_error: Optional[str] = None
            self.collection_task: Optional[asyncio.Task] = None
            self.is_running = False
            self.update_interval = 2  # Update every 2 seconds
            self.cache_ttl = 5  # Cache is valid for 5 seconds
            self._lock = asyncio.Lock()
            self._initialized = True
            logger.info("SessionsCacheService initialized")

    async def start(self):
        """Start the background sessions collection"""
        if self.is_running:
            logger.warning("Sessions collection already running")
            return

        self.is_running = True
        self.collection_task = asyncio.create_task(self._collect_sessions_loop())
        logger.info("Started background sessions collection")

    async def stop(self):
        """Stop the background sessions collection"""
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background sessions collection")

    async def get_cached_sessions(self, user_id: int = None, user_type: str = None, db = None) -> List[Dict]:
        """
        Get cached sessions filtered by user permissions
        Returns cached data if available and fresh, otherwise triggers a refresh
        """
        # Check if cache is still valid
        if self.last_update and datetime.utcnow() - self.last_update < timedelta(seconds=self.cache_ttl):
            return await self._filter_sessions_for_user(self.sessions_cache, user_id, user_type, db)

        # If cache is stale and no background update is running, trigger one
        if not self.collection_task or self.collection_task.done():
            logger.info("Cache is stale and no update running, triggering refresh")
            await self._collect_all_sessions()

        # Return whatever we have (even if stale) to avoid blocking
        return await self._filter_sessions_for_user(self.sessions_cache, user_id, user_type, db)

    async def _filter_sessions_for_user(self, sessions: List[Dict], user_id: int = None, user_type: str = None, db = None) -> List[Dict]:
        """Filter sessions based on user permissions"""
        if not user_id or not user_type or not db:
            # Admin or no filtering needed
            return sessions

        if user_type == "admin":
            return sessions

        # For local users, filter by permissions
        from ..models.user_permission import UserPermission

        # Get server IDs this user has permission to view sessions for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.can_view_sessions == True
        ).all()

        allowed_server_ids = [perm.server_id for perm in permissions]

        # Filter sessions to only those from allowed servers
        filtered_sessions = [
            session for session in sessions
            if session.get("server_id") in allowed_server_ids
        ]

        return filtered_sessions

    async def _collect_sessions_loop(self):
        """Main loop that collects sessions from all servers"""
        while self.is_running:
            try:
                await self._collect_all_sessions()
                # Wait before next collection
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in sessions collection loop: {e}")
                self.last_error = str(e)
                await asyncio.sleep(5)  # Wait longer on error

    async def _collect_all_sessions(self):
        """Collect sessions from all configured servers"""
        from ..core.database import SessionLocal
        from ..models.server import Server
        from ..models.playback_analytics import PlaybackEvent
        from ..providers.factory import ProviderFactory
        from datetime import datetime

        db = SessionLocal()
        try:
            # Get all active servers
            servers = db.query(Server).filter(Server.enabled == True).all()

            all_sessions = []
            errors = []

            # Use asyncio.gather to fetch from all servers concurrently
            tasks = []
            for server in servers:
                tasks.append(self._fetch_server_sessions(server, db))

            # Gather all results
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                    logger.error(f"Error fetching sessions: {result}")
                elif result:
                    all_sessions.extend(result)

            # Update cache with lock to ensure thread safety
            async with self._lock:
                self.sessions_cache = all_sessions
                self.last_update = datetime.utcnow()
                if errors:
                    self.last_error = f"Errors from {len(errors)} servers: {', '.join(errors[:3])}"
                else:
                    self.last_error = None

            logger.info(f"Cached {len(all_sessions)} sessions from {len(servers)} servers")

        except Exception as e:
            logger.error(f"Error collecting sessions: {e}")
            self.last_error = str(e)
        finally:
            db.close()

    async def _fetch_server_sessions(self, server, db):
        """Fetch sessions from a single server"""
        try:
            from ..providers.factory import ProviderFactory
            from datetime import datetime

            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()

            # Add server info to each session
            for session in sessions:
                session["server_name"] = server.name
                session["server_type"] = server.type.value
                session["server_id"] = server.id

                # Track analytics for this session
                try:
                    await self._track_session_analytics(db, server.id, session)
                except Exception as analytics_error:
                    logger.debug(f"Analytics tracking error for {server.name}: {analytics_error}")

            return sessions

        except Exception as e:
            logger.error(f"Failed to fetch sessions from server {server.name}: {e}")
            raise

    async def _track_session_analytics(self, db, server_id: int, session: dict):
        """Track or update playback analytics for a session"""
        from ..models.playback_analytics import PlaybackEvent
        from datetime import datetime

        try:
            # Check if we already have a record for this session
            existing_event = db.query(PlaybackEvent).filter(
                PlaybackEvent.server_id == server_id,
                PlaybackEvent.provider_session_id == session.get('session_id')
            ).first()

            if existing_event:
                # Update existing event with latest progress
                existing_event.progress_ms = session.get('progress_ms', 0)
                existing_event.progress_percent = session.get('progress_percent', 0)
                existing_event.state = session.get('state', 'unknown')
                existing_event.updated_at = datetime.utcnow()

                # Check if this should be marked as complete (>90% watched)
                if session.get('progress_percent', 0) >= 90:
                    existing_event.is_complete = True

            else:
                # Create new playback event
                new_event = PlaybackEvent(
                    server_id=server_id,
                    provider_session_id=session.get('session_id'),
                    provider_user_id=session.get('user_id'),
                    provider_media_id=session.get('media_id'),
                    username=session.get('username'),
                    media_title=session.get('media_title') or session.get('title') or session.get('full_title'),
                    media_type=session.get('media_type', 'unknown'),
                    grandparent_title=session.get('grandparent_title'),
                    parent_title=session.get('parent_title'),
                    year=session.get('year'),
                    library_section=session.get('library_section'),
                    device=session.get('device'),
                    platform=session.get('platform'),
                    product=session.get('product'),
                    video_decision=session.get('video_decision', 'unknown'),
                    original_resolution=session.get('original_resolution'),
                    original_bitrate=session.get('original_bitrate'),
                    video_codec=session.get('video_codec'),
                    audio_codec=session.get('audio_codec'),
                    progress_ms=session.get('progress_ms', 0),
                    progress_percent=session.get('progress_percent', 0),
                    started_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    is_complete=session.get('progress_percent', 0) >= 90
                )
                db.add(new_event)

            db.commit()

        except Exception as e:
            logger.debug(f"Error tracking analytics for session: {e}")
            db.rollback()

    def get_cache_status(self) -> Dict:
        """Get current cache status"""
        return {
            "is_running": self.is_running,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_error": self.last_error,
            "session_count": len(self.sessions_cache),
            "cache_age_seconds": (datetime.utcnow() - self.last_update).total_seconds() if self.last_update else None
        }

# Global instance
sessions_cache_service = SessionsCacheService()