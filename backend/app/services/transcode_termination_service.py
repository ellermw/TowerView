"""
Service for automatically terminating 4K transcodes
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, ClassVar
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import SystemSettings, Session as SessionModel, Server, AuditLog
from ..providers.factory import ProviderFactory
from ..core.database import get_db

logger = logging.getLogger(__name__)


class TranscodeTerminationService:
    """Service to handle automatic termination of 4K transcodes"""

    # Settings keys
    AUTO_TERMINATE_ENABLED = "4k_transcode_auto_terminate_enabled"
    AUTO_TERMINATE_MESSAGE = "4k_transcode_auto_terminate_message"
    AUTO_TERMINATE_SERVERS = "4k_transcode_auto_terminate_servers"  # List of server IDs to apply to

    # Default message
    DEFAULT_MESSAGE = "4K transcoding is not allowed. Please use a client that supports direct play or choose a lower quality version."

    # Track session start times
    _session_start_times: ClassVar[Dict[str, datetime]] = {}  # Track when we first saw a 4K transcode
    _lock: ClassVar[Optional[asyncio.Lock]] = None  # Protect shared class variables from race conditions
    GRACE_PERIOD = timedelta(seconds=5)  # Allow 5 seconds before termination

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the asyncio lock (must be created within event loop)"""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def get_settings(cls, db: Session) -> Dict[str, Any]:
        """Get current auto-termination settings"""
        enabled_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_ENABLED).first()
        message_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_MESSAGE).first()
        servers_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_SERVERS).first()

        return {
            "enabled": enabled_setting.value if enabled_setting else False,
            "message": message_setting.value if message_setting else cls.DEFAULT_MESSAGE,
            "server_ids": servers_setting.value if servers_setting else []
        }

    @classmethod
    def update_settings(cls, db: Session, enabled: bool, message: str, server_ids: List[int], updated_by_id: int):
        """Update auto-termination settings"""
        # Update or create enabled setting
        enabled_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_ENABLED).first()
        if enabled_setting:
            enabled_setting.value = enabled
            enabled_setting.updated_at = datetime.utcnow()
            enabled_setting.updated_by_id = updated_by_id
        else:
            enabled_setting = SystemSettings(
                key=cls.AUTO_TERMINATE_ENABLED,
                value=enabled,
                category="transcode",
                description="Enable automatic termination of 4K to 1080p or below transcodes",
                updated_by_id=updated_by_id
            )
            db.add(enabled_setting)

        # Update or create message setting
        message_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_MESSAGE).first()
        if message_setting:
            message_setting.value = message
            message_setting.updated_at = datetime.utcnow()
            message_setting.updated_by_id = updated_by_id
        else:
            message_setting = SystemSettings(
                key=cls.AUTO_TERMINATE_MESSAGE,
                value=message,
                category="transcode",
                description="Message to display when terminating 4K transcodes (Plex only)",
                updated_by_id=updated_by_id
            )
            db.add(message_setting)

        # Update or create servers setting
        servers_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_SERVERS).first()
        if servers_setting:
            servers_setting.value = server_ids
            servers_setting.updated_at = datetime.utcnow()
            servers_setting.updated_by_id = updated_by_id
        else:
            servers_setting = SystemSettings(
                key=cls.AUTO_TERMINATE_SERVERS,
                value=server_ids,
                category="transcode",
                description="List of server IDs to apply auto-termination to",
                updated_by_id=updated_by_id
            )
            db.add(servers_setting)

        db.commit()
        logger.info(f"4K transcode auto-termination settings updated: enabled={enabled}, servers={server_ids}")

    @classmethod
    async def check_and_terminate_4k_transcodes(cls, sessions: List[Dict[str, Any]], db: Session) -> int:
        """
        Check sessions and terminate any 4K transcodes to 1080p or below after 5-second grace period
        Returns the number of terminated sessions
        """
        settings = cls.get_settings(db)

        logger.info(f"4K Transcode Check: Feature enabled={settings['enabled']}, Enabled servers={settings['server_ids']}, Total sessions={len(sessions)}")

        # Skip if feature is disabled
        if not settings["enabled"]:
            logger.info("4K transcode auto-termination is disabled, skipping check")
            return 0

        terminated_count = 0
        now = datetime.utcnow()

        # Clean up old session start times (remove sessions that are no longer active)
        # Also remove entries older than 1 hour to prevent memory leak
        async with cls._get_lock():
            active_session_keys = {
                f"{s.get('server_id')}_{s.get('session_id')}"
                for s in sessions
                if s.get('server_id') and s.get('session_id')
            }
            # Remove both inactive and very old sessions
            cutoff_time = now - timedelta(hours=1)
            cls._session_start_times = {
                k: v for k, v in cls._session_start_times.items()
                if k in active_session_keys and v > cutoff_time
            }
            if len(cls._session_start_times) > 0:
                logger.debug(f"Cleaned up session tracking, {len(cls._session_start_times)} sessions still tracked")

        for session in sessions:
            # Skip if server is not in the enabled list
            server_id = session.get("server_id")
            session_id = session.get("session_id")
            username = session.get("username", "Unknown")
            title = session.get("title", "Unknown")

            logger.info(f"Checking session: server_id={server_id}, session_id={session_id}, user={username}, title={title}")

            if server_id not in settings["server_ids"]:
                logger.info(f"  ➜ SKIP: Server {server_id} not in enabled list {settings['server_ids']}")
                continue

            # Check if this is a 4K to 1080p or below transcode
            is_4k_transcode = cls._is_4k_downscale_transcode(session)
            logger.info(f"  ➜ Is 4K transcode: {is_4k_transcode} (video_decision={session.get('video_decision')}, original_res={session.get('original_resolution')}, stream_res={session.get('stream_resolution')}, is_4k={session.get('is_4k')})")

            if not is_4k_transcode:
                continue

            logger.info(f"  ➜ 4K TRANSCODE DETECTED! Processing termination logic for {title}")

            # Send notification about 4K transcode detection
            await cls._send_notification(
                "4k_transcode_detected",
                f"4K transcode detected: {username} watching {title}",
                {
                    "username": username,
                    "title": title,
                    "server_id": server_id,
                    "original_resolution": session.get('original_resolution'),
                    "stream_resolution": session.get('stream_resolution')
                }
            )

            # Create session tracking key (server_id + session_id) for per-session grace period tracking
            session_track_key = f"{server_id}_{session.get('session_id')}"
            logger.info(f"  ➜ Session tracking key: {session_track_key}")

            # Check session state and decide on termination with lock protection
            # Determine termination decision inside lock, execute outside
            should_terminate = False
            try:
                logger.info(f"  ➜ Acquiring lock to check session state...")
                lock = cls._get_lock()
                logger.info(f"  ➜ Got lock object: {lock}")
                async with lock:
                    logger.info(f"  ➜ Inside lock context! Tracked sessions: {list(cls._session_start_times.keys())}")

                    # Track when we first saw this 4K transcode
                    if session_track_key not in cls._session_start_times:
                        logger.info(f"  ➜ NEW 4K transcode! Starting grace period for {session_track_key}")
                        cls._session_start_times[session_track_key] = now
                        logger.info(f"  ➜ Started tracking 4K transcode session {session_track_key} - grace period starts now")
                        should_terminate = False
                    else:
                        # Check if grace period has passed
                        logger.info(f"  ➜ Session {session_track_key} already being tracked")
                        session_start = cls._session_start_times[session_track_key]
                        elapsed = now - session_start
                        logger.info(f"  ➜ Time elapsed: {elapsed.total_seconds():.1f}s, Grace period: {cls.GRACE_PERIOD.total_seconds()}s")
                        if now - session_start < cls.GRACE_PERIOD:
                            remaining = (cls.GRACE_PERIOD - (now - session_start)).total_seconds()
                            logger.info(f"  ➜ Session {session_track_key} in grace period, {remaining:.1f}s remaining")
                            should_terminate = False
                        else:
                            logger.info(f"  ➜ Grace period EXPIRED! Proceeding to terminate...")
                            should_terminate = True
            except Exception as lock_error:
                logger.error(f"  ➜ ERROR acquiring/using lock: {lock_error}", exc_info=True)
                continue

            # Skip termination if not ready (grace period or new session)
            if not should_terminate:
                continue

            username = session.get("username", "")

            # Get the server
            server = db.query(Server).filter_by(id=session["server_id"]).first()
            if not server:
                logger.error(f"Server {session['server_id']} not found")
                continue

            try:
                # Create provider and terminate session
                provider = ProviderFactory.create_provider(server, db)

                # Only send message for Plex servers (Emby/Jellyfin don't support message parameter)
                if server.type.value == "plex":
                    termination_message = settings["message"]
                    logger.info(f"  ➜ Server type: plex, Message: {termination_message}")
                    success = await provider.terminate_session(
                        provider_session_id=session["session_id"],
                        message=termination_message
                    )
                else:
                    logger.info(f"  ➜ Server type: {server.type.value}, Message: None (non-Plex)")
                    success = await provider.terminate_session(
                        provider_session_id=session["session_id"]
                    )

                if success:
                    terminated_count += 1

                    # Remove from tracking
                    async with cls._get_lock():
                        if session_track_key in cls._session_start_times:
                            del cls._session_start_times[session_track_key]

                    # Log the termination with System as actor
                    from ..services.audit_service import AuditService
                    AuditService.log_action(
                        db=db,
                        actor=None,  # None will show as "System"
                        action="SESSION_TERMINATED",
                        target="session",
                        target_name=f"{username} - {session.get('title')}",
                        details={
                            "reason": "4K transcode auto-termination",
                            "server_id": server.id,
                            "server_name": server.name,
                            "server_type": str(server.type.value),
                            "username": username,
                            "title": session.get("title"),
                            "original_resolution": session.get("original_resolution"),
                            "stream_resolution": session.get("stream_resolution"),
                            "message_sent": termination_message if termination_message else "No message (non-Plex server)"
                        },
                        request=None
                    )

                    logger.info(f"Terminated 4K transcode for user {username} on {server.name}: {session.get('title')}")

                    # Send success notification
                    await cls._send_notification(
                        "4k_transcode_terminated",
                        f"Successfully terminated 4K transcode: {username} - {title}",
                        {
                            "username": username,
                            "title": title,
                            "server_name": server.name,
                            "server_id": server.id
                        }
                    )
                else:
                    logger.warning(f"Failed to terminate 4K transcode for {username} on {server.name}")

                    # Send failure notification
                    await cls._send_notification(
                        "4k_transcode_termination_failed",
                        f"Failed to terminate 4K transcode: {username} - {title}",
                        {
                            "username": username,
                            "title": title,
                            "server_name": server.name,
                            "server_id": server.id
                        }
                    )

            except Exception as e:
                logger.error(f"Error terminating session: {str(e)}")
                continue

        return terminated_count

    @classmethod
    async def _send_notification(cls, notification_type: str, message: str, details: Dict[str, Any]):
        """Send a WebSocket notification to all connected clients"""
        try:
            from ..api.routes.websocket import manager
            await manager.broadcast_notification({
                "type": "notification",
                "notification_type": notification_type,
                "message": message,
                "details": details
            })
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    @staticmethod
    def _is_4k_downscale_transcode(session: Dict[str, Any]) -> bool:
        """Check if a session is a 4K to 1080p or below transcode"""
        # Must be transcoding
        if session.get("video_decision") != "transcode":
            return False

        # Check if original is 4K
        original_res = session.get("original_resolution", "").lower()
        is_4k_source = original_res in ["4k", "2160p", "2160"] or session.get("is_4k", False)

        if not is_4k_source:
            return False

        # Check if transcoding to 1080p or below
        stream_res = session.get("stream_resolution", "").lower()

        # List of resolutions that are 1080p or below
        low_res = ["1080p", "1080", "720p", "720", "480p", "480", "360p", "360", "240p", "240", "sd"]

        # Check if stream resolution indicates downscaling
        for res in low_res:
            if res in stream_res:
                return True

        # Also check numeric values if present
        if stream_res.replace("p", "").isdigit():
            res_num = int(stream_res.replace("p", ""))
            if res_num <= 1080:
                return True

        return False