"""
Session management endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from ....core.database import get_db
from ....core.security import get_current_admin_user, get_current_admin_or_local_user, get_current_user
from ....models.user import User, UserType
from ....schemas.session import LiveSessionResponse, SessionResponse
from ....services.server_service import ServerService
from ....services.audit_service import AuditService
from ....services.user_service import UserService
from ....providers.factory import ProviderFactory
from ....models.playback_analytics import PlaybackEvent
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sessions", response_model=List[LiveSessionResponse])
async def get_all_sessions(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get active sessions from all servers accessible by the user (from cache)"""
    from ....services.sessions_cache_service import sessions_cache_service

    # Debug logging
    logger.info(f"Sessions API called - User: {current_user.username}, Type: {current_user.type.value}, ID: {current_user.id}")

    # Get sessions from cache instead of hitting servers directly
    cached_sessions = await sessions_cache_service.get_cached_sessions(
        user_id=current_user.id,
        user_type=current_user.type.value,
        db=db
    )

    logger.info(f"Returning {len(cached_sessions)} sessions to user {current_user.username}")

    # Debug logging for Together session
    for session in cached_sessions:
        if "Together" in session.get("title", ""):
            logger.info(f"Together session data: is_hdr={session.get('is_hdr')}, quality_profile={session.get('quality_profile')}")
            break

    return cached_sessions


@router.get("/servers/{server_id}/sessions", response_model=List[LiveSessionResponse])
async def get_server_sessions(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get active sessions for a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    try:
        provider = ProviderFactory.create_provider(server, db)
        sessions = await provider.list_active_sessions()
        # Add server info to each session
        for session in sessions:
            session["server_name"] = server.name
            session["server_type"] = server.type.value
            session["server_id"] = server.id
        return sessions

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sessions: {str(e)}"
        )


from pydantic import BaseModel
from typing import Optional

class TerminateSessionRequest(BaseModel):
    message: Optional[str] = None

@router.post("/servers/{server_id}/sessions/{session_id}/terminate")
async def terminate_session(
    server_id: int,
    session_id: str,
    request: Request,
    body: Optional[TerminateSessionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Terminate an active session on a server"""
    server_service = ServerService(db)
    user_service = UserService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Permission checking based on user type
    if current_user.type == UserType.admin:
        # Admins can terminate sessions on servers they own
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage this server"
            )
    elif current_user.type in [UserType.staff, UserType.support]:
        # Staff/Support users need specific permission to terminate sessions
        server_permission = user_service.get_user_server_permission(current_user.id, server_id)
        if not server_permission or not server_permission.can_terminate_sessions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to terminate sessions on this server"
            )
    elif current_user.type == UserType.local_user:
        # Local users need specific permission to manage servers
        server_permission = user_service.get_user_server_permission(current_user.id, server_id)
        if not server_permission or not server_permission.can_manage_servers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to terminate sessions on this server"
            )
    else:
        # Media users need to check server-level permissions
        server_permission = user_service.get_user_server_permission(current_user.id, server_id)
        if not server_permission or not server_permission.can_manage_server:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to terminate sessions on this server"
            )

    try:
        logger.info(f"Attempting to terminate session {session_id} on server {server_id} ({server.name})")
        provider = ProviderFactory.create_provider(server, db)

        # Get session info BEFORE terminating (for audit log)
        session_username = "Unknown"
        session_found = False

        try:
            sessions = await provider.list_active_sessions()
            logger.info(f"Found {len(sessions)} active sessions on server {server.name}")
            logger.info(f"Looking for session_id: {session_id}")

            for session in sessions:
                # Different providers use different field names
                current_session_id = session.get("session_id") or session.get("Id")
                logger.debug(f"Checking session {current_session_id} (looking for {session_id})")

                # Debug logging to help diagnose username issues
                if current_session_id == session_id:
                    logger.info(f"Found matching session. Available keys: {list(session.keys())}")
                    logger.info(f"Session data sample - username: {session.get('username')}, UserName: {session.get('UserName')}, user_name: {session.get('user_name')}")

                    # Try various username field names used by different providers
                    session_username = (
                        session.get("username") or
                        session.get("UserName") or
                        session.get("user_name") or
                        "Unknown"
                    )
                    logger.info(f"Extracted username: {session_username}")
                    session_found = True

                    # For media users, verify they're terminating their own session
                    if current_user.type == UserType.media_user:
                        if session_username.lower() != current_user.username.lower():
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only terminate your own sessions"
                            )
                    break

            # Log if session not found
            if not session_found:
                logger.warning(f"Session {session_id} not found in active sessions list - will proceed with 'Unknown' username")
                logger.warning(f"Available session IDs were: {[s.get('session_id') or s.get('Id') for s in sessions]}")

            # If session not found and user is media user, return error
            if not session_found and current_user.type == UserType.media_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not get session info before termination: {e}")
            # Continue anyway - we can still try to terminate

        # Pass message to provider if it's a Plex server
        if server.type.value == "plex" and body and body.message:
            success = await provider.terminate_session(session_id, message=body.message)
        else:
            success = await provider.terminate_session(session_id)
        logger.info(f"Termination result for session {session_id}: {success}")

        if not success:
            # Check if this is a Plex server for better error message
            if server.type.value == "plex":
                detail = "Plex Pass session termination failed. Possible reasons: 1) Termination disabled in server settings, 2) Token lacks admin permissions, 3) Local session cannot be terminated remotely, or 4) Server version doesn't support these endpoints."
            else:
                detail = "Failed to terminate session"

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail
            )

        # Log the action with the username we captured earlier
        AuditService.log_session_terminated(
            db, current_user, session_id, session_username, server.name, request
        )

        return {"message": "Session terminated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to terminate session: {str(e)}"
        )


@router.get("/sessions/cache-status")
async def get_sessions_cache_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get the current status of the sessions cache"""
    from ....services.sessions_cache_service import sessions_cache_service
    return sessions_cache_service.get_cache_status()


@router.post("/sessions/refresh-cache")
async def refresh_sessions_cache(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Manually trigger a refresh of the sessions cache"""
    from ....services.sessions_cache_service import sessions_cache_service

    # Force a cache refresh
    await sessions_cache_service._collect_all_sessions()

    return {
        "message": "Cache refresh triggered",
        "status": sessions_cache_service.get_cache_status()
    }


@router.get("/sessions/counts")
async def get_session_counts(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get active session counts per server"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    session_counts = {}
    logger.debug(f"[SESSION COUNTS] Processing {len(servers)} servers")

    for server in servers:
        if not server.enabled:
            session_counts[server.id] = 0
            logger.debug(f"[SESSION COUNTS] {server.name}: 0 (disabled)")
            continue

        try:
            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()
            session_counts[server.id] = len(sessions)
            logger.debug(f"[SESSION COUNTS] {server.name}: {len(sessions)} sessions")
        except Exception as e:
            logger.error(f"[SESSION COUNTS] ERROR - Failed to fetch session count from server {server.name}: {e}")
            session_counts[server.id] = 0

    total_count = sum(session_counts.values())
    logger.debug(f"[SESSION COUNTS] Total sessions across all servers: {total_count}")
    return session_counts


@router.get("/sessions/bandwidth-history")
async def get_bandwidth_history(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get bandwidth history for the last 90 seconds"""
    from ....services.bandwidth_cache import get_bandwidth_history as get_cache

    # Get the bandwidth history from cache
    history_data = await get_cache()

    return {
        "history": history_data.get("history", []),
        "stats": history_data.get("stats", {}),
        "cache_size": history_data.get("cache_size", 0),
        "max_points": history_data.get("max_points", 18),
        "interval_seconds": 5
    }


async def track_session_analytics(db: Session, server_id: int, session: dict):
    """Track analytics for active sessions (helper function)"""
    try:
        # Extract relevant fields
        user_id = session.get("user_id") or session.get("UserId")
        username = session.get("username") or session.get("UserName", "Unknown")
        media_type = session.get("media_type") or session.get("Type", "Unknown")
        title = session.get("title") or session.get("NowPlayingItem", {}).get("Name", "Unknown")

        # Get or create the parent item (movie/show)
        parent_title = title
        season_episode = None

        if media_type == "Episode":
            parent_title = session.get("grandparent_title") or session.get("SeriesName", title)
            season = session.get("parent_index") or session.get("ParentIndexNumber", 0)
            episode = session.get("index") or session.get("IndexNumber", 0)
            season_episode = f"S{season:02d}E{episode:02d}"

        # Check if this session is already being tracked
        session_key = session.get("session_id") or session.get("Id")
        existing_event = db.query(PlaybackEvent).filter(
            PlaybackEvent.session_key == session_key,
            PlaybackEvent.server_id == server_id,
            PlaybackEvent.is_complete == False
        ).first()

        if existing_event:
            # Update progress
            existing_event.progress_percent = session.get("progress_percent", 0)
            existing_event.updated_at = datetime.utcnow()
            existing_event.is_complete = session.get("progress_percent", 0) >= 90
        else:
            # Create new event
            new_event = PlaybackEvent(
                server_id=server_id,
                user_id=user_id,
                username=username,
                media_type=media_type,
                title=parent_title,
                season_episode=season_episode,
                library=session.get("library_name", "Unknown"),
                device=session.get("device", "Unknown"),
                platform=session.get("platform", "Unknown"),
                product=session.get("product", "Unknown"),
                player=session.get("player", "Unknown"),
                quality=session.get("quality_profile", "Unknown"),
                is_direct_play=not session.get("is_transcoding", False),
                started_at=datetime.utcnow(),
                session_key=session_key,
                progress_percent=session.get("progress_percent", 0),
                updated_at=datetime.utcnow(),
                is_complete=session.get("progress_percent", 0) >= 90
            )
            db.add(new_event)

        db.commit()

    except Exception as e:
        logger.error(f"Error tracking analytics for session: {e}")
        db.rollback()