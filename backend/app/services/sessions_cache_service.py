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

        # Media users can only see sessions from servers marked as visible to them
        if user_type == "media_user":
            from ..models.server import Server
            from ..models.user import User

            # Get servers that are visible to media users
            visible_servers = db.query(Server).filter(
                Server.visible_to_media_users == True,
                Server.enabled == True
            ).all()

            visible_server_ids = [server.id for server in visible_servers]

            # Debug logging
            logger.info(f"Media user filtering - User ID: {user_id}, Type: {user_type}")
            logger.info(f"Visible server IDs: {visible_server_ids}")
            logger.info(f"Total sessions before filter: {len(sessions)}")
            logger.info(f"Session server IDs: {[s.get('server_id') for s in sessions]}")

            # Get the current media user's username
            current_user = db.query(User).filter(User.id == user_id).first()
            current_username = current_user.username.lower() if current_user else ""

            # Filter sessions to only those from visible servers and censor usernames
            filtered_sessions = []
            for session in sessions:
                session_server_id = session.get("server_id")
                logger.info(f"Checking session - Server ID: {session_server_id}, in visible list: {session_server_id in visible_server_ids}")
                if session_server_id in visible_server_ids:
                    # Make a copy of the session to avoid modifying the cache
                    session_copy = session.copy()

                    # Censor username if it's not the current user
                    username = session_copy.get("username", "")
                    if username and username.lower() != current_username:
                        # Keep first letter, replace rest with asterisks
                        session_copy["username"] = username[0] + "*" * (len(username) - 1)

                    filtered_sessions.append(session_copy)

            logger.info(f"Filtered sessions count: {len(filtered_sessions)}")
            return filtered_sessions

        # Support users can also see all sessions (view-only role)
        if user_type == "support":
            return sessions

        # For staff/local users, filter by permissions
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

            # Check for and terminate 4K transcodes if enabled
            logger.info(f"About to check for 4K transcodes - {len(all_sessions)} sessions collected")
            try:
                from ..services.transcode_termination_service import TranscodeTerminationService
                terminated_count = await TranscodeTerminationService.check_and_terminate_4k_transcodes(
                    all_sessions, db
                )
                logger.info(f"4K transcode check completed - terminated {terminated_count} sessions")
                if terminated_count > 0:
                    logger.info(f"Auto-terminated {terminated_count} 4K transcode sessions")
            except Exception:
                logger.exception("Error in auto-termination check")

            # Sync watch history from Plex servers (every 10th poll = every 20 seconds)
            if not hasattr(self, '_history_poll_counter'):
                self._history_poll_counter = 0
            self._history_poll_counter += 1

            if self._history_poll_counter >= 10:
                self._history_poll_counter = 0
                try:
                    await self._sync_watch_history(servers, db)
                except Exception as e:
                    logger.error(f"Error syncing watch history: {e}")

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

    async def _sync_watch_history(self, servers, db):
        """Sync watch history from Plex servers to capture missed sessions"""
        from ..providers.factory import ProviderFactory
        from ..models.playback_analytics import PlaybackEvent

        for server in servers:
            # Only sync history for Plex servers
            if server.type.value != 'plex':
                continue

            try:
                provider = ProviderFactory.create_provider(server, db)

                # Check if provider has get_watch_history method
                if not hasattr(provider, 'get_watch_history'):
                    continue

                # Fetch last 1 hour of history
                history_items = await provider.get_watch_history(hours=1)

                logger.info(f"Processing {len(history_items)} history items from {server.name}")

                for item in history_items:
                    try:
                        # Check if we already have this event
                        existing = db.query(PlaybackEvent).filter(
                            PlaybackEvent.server_id == server.id,
                            PlaybackEvent.provider_media_id == item.get('media_id'),
                            PlaybackEvent.username == item.get('username')
                        ).order_by(PlaybackEvent.updated_at.desc()).first()

                        # If event exists and was updated recently (within 2 hours), skip
                        if existing and (datetime.utcnow() - existing.updated_at).total_seconds() < 7200:
                            continue

                        # Create new playback event from history
                        new_event = PlaybackEvent(
                            server_id=server.id,
                            provider_session_id=item.get('session_id'),
                            provider_user_id=item.get('user_id'),
                            provider_media_id=item.get('media_id'),
                            username=item.get('username'),
                            media_title=item.get('media_title'),
                            media_type=item.get('media_type', 'unknown'),
                            grandparent_title=item.get('grandparent_title'),
                            parent_title=item.get('parent_title'),
                            season_number=item.get('season_number'),
                            episode_number=item.get('episode_number'),
                            year=item.get('year'),
                            library_section=item.get('library_section'),
                            progress_percent=item.get('progress_percent', 100.0),
                            started_at=item.get('viewed_at'),
                            updated_at=item.get('viewed_at'),
                            is_complete=item.get('is_complete', True)
                        )
                        db.add(new_event)
                        logger.info(f"Added history event: {item.get('username')} watched {item.get('media_title')}")

                    except Exception as e:
                        logger.debug(f"Error processing history item: {e}")
                        continue

                db.commit()

            except Exception as e:
                logger.error(f"Error syncing history from {server.name}: {e}")
                db.rollback()
                continue

    async def _track_session_analytics(self, db, server_id: int, session: dict):
        """Track or update playback analytics for a session"""
        from ..models.playback_analytics import PlaybackEvent
        from datetime import datetime

        try:
            # Match by media_id, username, and server_id for the current viewing session
            # This ensures each piece of media gets its own event, even if session IDs are reused
            media_id = session.get('media_id')
            username = session.get('username')
            media_title = session.get('media_title') or session.get('title') or session.get('full_title')

            # Find existing event for this specific media being watched recently (within last hour)
            existing_event = None
            if media_id and username:
                existing_event = db.query(PlaybackEvent).filter(
                    PlaybackEvent.server_id == server_id,
                    PlaybackEvent.provider_media_id == media_id,
                    PlaybackEvent.username == username,
                    PlaybackEvent.updated_at > datetime.utcnow() - timedelta(hours=1)
                ).order_by(PlaybackEvent.updated_at.desc()).first()

            if existing_event:
                # Update existing event with latest progress
                existing_event.provider_session_id = session.get('session_id')  # Update session ID
                existing_event.progress_ms = session.get('progress_ms', 0)
                existing_event.progress_percent = session.get('progress_percent', 0)
                existing_event.updated_at = datetime.utcnow()

                # Check if this should be marked as complete (>50% watched)
                if session.get('progress_percent', 0) >= 50:
                    existing_event.is_complete = True

            if not existing_event:
                # Create new playback event
                # Determine if this is hardware transcoding (video transcode) vs software transcode (audio/other)
                is_hw = False
                if session.get('video_decision') == 'transcode':
                    # HW transcode if any of the HW transcode flags are True
                    is_hw = (
                        session.get('transcode_hw_requested') or
                        session.get('transcode_hw_full_pipeline') or
                        session.get('transcode_hw_decode') or
                        session.get('transcode_hw_encode')
                    ) or False

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
                    season_number=session.get('season_number'),
                    episode_number=session.get('episode_number'),
                    year=session.get('year'),
                    library_section=session.get('library_section'),
                    device=session.get('device'),
                    platform=session.get('platform'),
                    product=session.get('product'),
                    video_decision=session.get('video_decision', 'unknown'),
                    is_hw_transcode=is_hw,
                    original_resolution=session.get('original_resolution'),
                    original_bitrate=session.get('original_bitrate'),
                    video_codec=session.get('video_codec'),
                    audio_codec=session.get('audio_codec'),
                    progress_ms=session.get('progress_ms', 0),
                    progress_percent=session.get('progress_percent', 0),
                    started_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    is_complete=session.get('progress_percent', 0) >= 50
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