"""
Service for automatically terminating 4K transcodes
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
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
    AUTO_TERMINATE_WHITELIST = "4k_transcode_auto_terminate_whitelist"  # List of usernames to exclude

    # Default message
    DEFAULT_MESSAGE = "4K transcoding is not allowed. Please use a client that supports direct play or choose a lower quality version."

    # Track recently terminated sessions to avoid duplicate terminations
    _terminated_sessions: Dict[str, datetime] = {}
    TERMINATION_COOLDOWN = timedelta(minutes=5)  # Don't re-terminate same user/title for 5 minutes

    @classmethod
    def get_settings(cls, db: Session) -> Dict[str, Any]:
        """Get current auto-termination settings"""
        enabled_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_ENABLED).first()
        message_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_MESSAGE).first()
        whitelist_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_WHITELIST).first()

        return {
            "enabled": enabled_setting.value if enabled_setting else False,
            "message": message_setting.value if message_setting else cls.DEFAULT_MESSAGE,
            "whitelist": whitelist_setting.value if whitelist_setting else []
        }

    @classmethod
    def update_settings(cls, db: Session, enabled: bool, message: str, whitelist: List[str], updated_by_id: int):
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
                description="Message to display when terminating 4K transcodes",
                updated_by_id=updated_by_id
            )
            db.add(message_setting)

        # Update or create whitelist setting
        whitelist_setting = db.query(SystemSettings).filter_by(key=cls.AUTO_TERMINATE_WHITELIST).first()
        if whitelist_setting:
            whitelist_setting.value = whitelist
            whitelist_setting.updated_at = datetime.utcnow()
            whitelist_setting.updated_by_id = updated_by_id
        else:
            whitelist_setting = SystemSettings(
                key=cls.AUTO_TERMINATE_WHITELIST,
                value=whitelist,
                category="transcode",
                description="List of usernames excluded from auto-termination",
                updated_by_id=updated_by_id
            )
            db.add(whitelist_setting)

        db.commit()
        logger.info(f"4K transcode auto-termination settings updated: enabled={enabled}")

    @classmethod
    async def check_and_terminate_4k_transcodes(cls, sessions: List[Dict[str, Any]], db: Session) -> int:
        """
        Check sessions and terminate any 4K transcodes to 1080p or below
        Returns the number of terminated sessions
        """
        settings = cls.get_settings(db)

        # Skip if feature is disabled
        if not settings["enabled"]:
            return 0

        terminated_count = 0
        now = datetime.utcnow()

        # Clean up old terminated session records
        cls._terminated_sessions = {
            k: v for k, v in cls._terminated_sessions.items()
            if now - v < cls.TERMINATION_COOLDOWN
        }

        for session in sessions:
            # Check if this is a 4K to 1080p or below transcode
            if not cls._is_4k_downscale_transcode(session):
                continue

            # Check if user is whitelisted
            username = session.get("username", "")
            if username in settings["whitelist"]:
                logger.debug(f"User {username} is whitelisted, skipping termination")
                continue

            # Check if we recently terminated this session
            session_key = f"{session.get('server_id')}_{username}_{session.get('title')}"
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
                    provider_type=server.server_type,
                    server_url=server.url,
                    api_token=server.get_decrypted_token(),
                    username=server.get_decrypted_username(),
                    password=server.get_decrypted_password(),
                    server_id=server.id
                )

                success = await provider.terminate_session(
                    session_id=session["session_id"],
                    message=settings["message"]
                )

                if success:
                    terminated_count += 1
                    cls._terminated_sessions[session_key] = now

                    # Log the termination
                    audit_log = AuditLog(
                        user_id=1,  # System action
                        action="terminate_session",
                        target_type="session",
                        target_id=session["session_id"],
                        details={
                            "reason": "4K transcode auto-termination",
                            "server_id": server.id,
                            "server_name": server.name,
                            "username": username,
                            "title": session.get("title"),
                            "original_resolution": session.get("original_resolution"),
                            "stream_resolution": session.get("stream_resolution"),
                            "message_sent": settings["message"]
                        },
                        ip_address="system",
                        user_agent="TranscodeTerminationService"
                    )
                    db.add(audit_log)
                    db.commit()

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