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

    # Track session start times and terminated sessions
    _session_start_times: ClassVar[Dict[str, datetime]] = {}  # Track when we first saw a 4K transcode
    _terminated_sessions: ClassVar[Dict[str, datetime]] = {}  # Track terminated sessions to avoid duplicates
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()  # Protect shared class variables from race conditions
    GRACE_PERIOD = timedelta(seconds=5)  # Allow 5 seconds before termination
    TERMINATION_COOLDOWN = timedelta(minutes=5)  # Don't re-terminate same user/title for 5 minutes

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

        # Skip if feature is disabled
        if not settings["enabled"]:
            return 0

        terminated_count = 0
        now = datetime.utcnow()

        # Clean up old records with lock protection
        async with cls._lock:
            cls._terminated_sessions = {
                k: v for k, v in cls._terminated_sessions.items()
                if now - v < cls.TERMINATION_COOLDOWN
            }

            # Clean up old session start times (remove sessions that are no longer active)
            active_session_keys = {
                f"{s.get('server_id')}_{s.get('session_id')}"
                for s in sessions
                if s.get('server_id') and s.get('session_id')
            }
            cls._session_start_times = {
                k: v for k, v in cls._session_start_times.items()
                if k in active_session_keys
            }

        for session in sessions:
            # Skip if server is not in the enabled list
            server_id = session.get("server_id")
            if server_id not in settings["server_ids"]:
                continue

            # Check if this is a 4K to 1080p or below transcode
            if not cls._is_4k_downscale_transcode(session):
                continue

            # Create session tracking key (server_id + session_id) for per-session grace period tracking
            session_track_key = f"{server_id}_{session.get('session_id')}"

            # Check session state and decide on termination with lock protection
            async with cls._lock:
                # Track when we first saw this 4K transcode
                if session_track_key not in cls._session_start_times:
                    cls._session_start_times[session_track_key] = now
                    logger.debug(f"Started tracking 4K transcode session {session_track_key}")
                    continue  # Don't terminate yet, start grace period

                # Check if grace period has passed
                session_start = cls._session_start_times[session_track_key]
                if now - session_start < cls.GRACE_PERIOD:
                    remaining = (cls.GRACE_PERIOD - (now - session_start)).total_seconds()
                    logger.debug(f"Session {session_track_key} in grace period, {remaining:.1f}s remaining")
                    continue

                # Check if we recently terminated this session (server_id + username + title) for cooldown across all sessions of same content
                username = session.get("username", "")
                session_key = f"{server_id}_{username}_{session.get('title')}"
                if session_key in cls._terminated_sessions:
                    logger.debug(f"Recently terminated session for {username}, skipping")
                    continue

            # Get the server
            server = db.query(Server).filter_by(id=session["server_id"]).first()
            if not server:
                logger.error(f"Server {session['server_id']} not found")
                continue

            try:
                # Create provider and terminate session
                provider = ProviderFactory.create_provider(
                    provider_type=server.type,
                    server_url=server.url,
                    api_token=server.get_decrypted_token(),
                    username=server.get_decrypted_username(),
                    password=server.get_decrypted_password(),
                    server_id=server.id
                )

                # Only send message for Plex servers
                termination_message = settings["message"] if server.type == "plex" else None

                success = await provider.terminate_session(
                    session_id=session["session_id"],
                    message=termination_message
                )

                if success:
                    terminated_count += 1

                    # Update shared state with lock protection
                    async with cls._lock:
                        cls._terminated_sessions[session_key] = now
                        # Remove from tracking
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
                            "reason": "4K transcode auto-termination (5-second grace period exceeded)",
                            "server_id": server.id,
                            "server_name": server.name,
                            "server_type": str(server.type.value),
                            "username": username,
                            "title": session.get("title"),
                            "original_resolution": session.get("original_resolution"),
                            "stream_resolution": session.get("stream_resolution"),
                            "grace_period_seconds": cls.GRACE_PERIOD.total_seconds(),
                            "message_sent": termination_message if termination_message else "No message (non-Plex server)"
                        },
                        request=None
                    )

                    logger.info(f"Terminated 4K transcode for user {username} on {server.name}: {session.get('title')}")
                else:
                    logger.warning(f"Failed to terminate 4K transcode for {username} on {server.name}")

            except Exception as e:
                logger.error(f"Error terminating session: {str(e)}")
                continue

        return terminated_count

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