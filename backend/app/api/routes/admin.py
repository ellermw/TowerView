from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_admin_user
from ...models.user import User
from ...schemas.server import ServerCreate, ServerResponse, ServerUpdate
from ...schemas.session import SessionResponse, LiveSessionResponse
from ...schemas.user import UserResponse, ServerUserResponse
from ...schemas.analytics import AnalyticsFilters, DashboardAnalyticsResponse
from ...services.server_service import ServerService
from ...services.analytics_service import AnalyticsService
from ...providers.factory import ProviderFactory
from ...models.playback_analytics import PlaybackEvent
from datetime import datetime

router = APIRouter()


@router.post("/servers", response_model=ServerResponse)
async def create_server(
    server_data: ServerCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new server"""
    server_service = ServerService(db)

    # Test connection to the server before creating
    try:
        from ...models.server import Server, ServerType
        temp_server = Server(
            name=server_data.name,
            type=server_data.type,
            base_url=server_data.base_url,
            owner_id=current_user.id
        )
        # Create provider with credentials directly
        print(f"Creating provider for {server_data.type} with credentials: {list(server_data.credentials.keys()) if server_data.credentials else 'None'}")
        if server_data.type == ServerType.plex:
            from ...providers.plex import PlexProvider
            provider = PlexProvider(temp_server, server_data.credentials)
        elif server_data.type == ServerType.emby:
            from ...providers.emby import EmbyProvider
            provider = EmbyProvider(temp_server, server_data.credentials)
        elif server_data.type == ServerType.jellyfin:
            from ...providers.jellyfin import JellyfinProvider
            provider = JellyfinProvider(temp_server, server_data.credentials)
        else:
            raise ValueError(f"Unsupported server type: {server_data.type}")

        if not await provider.connect():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to server with provided credentials"
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Server connection failed: {str(e)}"
        )

    server = server_service.create_server(server_data, current_user.id)
    return ServerResponse.from_orm(server)


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all servers"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)
    return [ServerResponse.from_orm(server) for server in servers]


@router.get("/servers/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get server details"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    return ServerResponse.from_orm(server)


@router.put("/servers/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update server details"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # If credentials are being updated, test the connection
    if server_data.credentials:
        try:
            from ...models.server import Server, ServerType
            temp_server = Server(
                name=server_data.name or server.name,
                type=server_data.type or server.type,
                base_url=server_data.base_url or server.base_url,
                owner_id=current_user.id
            )

            # Create provider with new credentials
            if temp_server.type == ServerType.plex:
                from ...providers.plex import PlexProvider
                provider = PlexProvider(temp_server, server_data.credentials)
            elif temp_server.type == ServerType.emby:
                from ...providers.emby import EmbyProvider
                provider = EmbyProvider(temp_server, server_data.credentials)
            elif temp_server.type == ServerType.jellyfin:
                from ...providers.jellyfin import JellyfinProvider
                provider = JellyfinProvider(temp_server, server_data.credentials)
            else:
                raise ValueError(f"Unsupported server type: {temp_server.type}")

            if not await provider.connect():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot connect to server with provided credentials"
                )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server connection failed: {str(e)}"
            )

    updated_server = server_service.update_server(server_id, server_data)
    return ServerResponse.from_orm(updated_server)


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    server_service.delete_server(server_id)
    return {"message": "Server deleted successfully"}


@router.get("/sessions", response_model=List[LiveSessionResponse])
async def get_all_sessions(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get active sessions from all servers"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    all_sessions = []

    for server in servers:
        if not server.enabled:
            continue

        try:
            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()

            # Add server info to each session
            for session in sessions:
                session["server_name"] = server.name
                session["server_type"] = server.type.value
                session["server_id"] = server.id

                # Track analytics for this session
                try:
                    await track_session_analytics(db, server.id, session)
                except Exception as analytics_error:
                    print(f"Analytics tracking error for {server.name}: {analytics_error}")

            all_sessions.extend(sessions)
        except Exception as e:
            print(f"Failed to fetch sessions from server {server.name}: {e}")
            continue

    return all_sessions


async def track_session_analytics(db: Session, server_id: int, session: dict):
    """Track or update playback analytics for a session"""
    try:
        # Check if we already have a record for this session
        session_key = f"{server_id}_{session.get('session_id', '')}"

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
        print(f"Error tracking analytics for session: {e}")
        db.rollback()


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


@router.post("/servers/{server_id}/sessions/{session_id}/terminate")
async def terminate_session(
    server_id: int,
    session_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Terminate a specific session"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    try:
        print(f"Attempting to terminate session {session_id} on server {server_id} ({server.name})")
        provider = ProviderFactory.create_provider(server, db)
        success = await provider.terminate_session(session_id)
        print(f"Termination result for session {session_id}: {success}")

        if not success:
            # Check if this is a Plex server for better error message
            if server.type.value == "plex":
                detail = "Plex Pass session termination failed. Possible reasons: 1) Termination disabled in server settings, 2) Token lacks admin permissions, 3) Local session cannot be terminated remotely, or 4) Server version doesn't support these endpoints."
            else:
                detail = "Failed to terminate session"

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )

        # Log the action
        from ...models.audit_log import AuditLog
        audit_log = AuditLog(
            actor_id=current_user.id,
            action="session_terminated",
            target=f"session:{session_id}",
            details={"server_id": server_id}
        )
        db.add(audit_log)
        db.commit()

        return {"message": "Session terminated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to terminate session: {str(e)}"
        )


@router.get("/servers/{server_id}/users", response_model=List[UserResponse])
async def get_server_users(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get users for a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    from ...services.user_service import UserService
    user_service = UserService(db)
    users = user_service.get_users_by_server(server_id)
    return [UserResponse.from_orm(user) for user in users]


@router.get("/sessions-old", response_model=List[SessionResponse])
async def get_all_sessions_old(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all active sessions across all servers (deprecated)"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    all_sessions = []
    for server in servers:
        if server.enabled:
            try:
                provider = ProviderFactory.create_provider(server, db)
                sessions = await provider.list_active_sessions()
                # Add server info to each session
                for session in sessions:
                    session["server_id"] = server.id
                    session["server_name"] = server.name
                    session["server_type"] = server.type.value
                all_sessions.extend(sessions)
            except Exception:
                # Skip servers that are unreachable
                continue

    return all_sessions


@router.get("/sessions/counts")
async def get_session_counts(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get active session counts per server"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    session_counts = {}
    print(f"[SESSION COUNTS] Processing {len(servers)} servers")

    for server in servers:
        if not server.enabled:
            session_counts[server.id] = 0
            print(f"[SESSION COUNTS] {server.name}: 0 (disabled)")
            continue

        try:
            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()
            session_counts[server.id] = len(sessions)
            print(f"[SESSION COUNTS] {server.name}: {len(sessions)} sessions")
        except Exception as e:
            print(f"[SESSION COUNTS] ERROR - Failed to fetch session count from server {server.name}: {e}")
            session_counts[server.id] = 0

    total_count = sum(session_counts.values())
    print(f"[SESSION COUNTS] Total sessions across all servers: {total_count}")
    return session_counts


@router.get("/users", response_model=List[ServerUserResponse])
async def get_all_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get users from all servers"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    all_users = []
    for server in servers:
        if not server.enabled:
            continue

        try:
            provider = ProviderFactory.create_provider(server, db)
            users = await provider.list_users()
            # Add server info to each user
            for user in users:
                user["server_name"] = server.name
                user["server_id"] = server.id
                user["server_type"] = server.type.value
            all_users.extend(users)
        except Exception as e:
            print(f"Failed to fetch users from server {server.name}: {e}")
            continue

    return all_users


@router.post("/analytics")
async def get_analytics(
    filters: AnalyticsFilters,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get analytics data for dashboard"""
    from ...services.analytics_service import AnalyticsService

    analytics_service = AnalyticsService(db)
    try:
        analytics_data = analytics_service.get_dashboard_analytics(filters)
        return analytics_data
    except Exception as e:
        # If analytics fails, return empty data to prevent dashboard crash
        print(f"Analytics query failed: {e}")
        return {
            "filters": filters,
            "top_users": [],
            "top_movies": [],
            "top_tv_shows": [],
            "top_libraries": [],
            "top_devices": [],
            "total_sessions": 0,
            "total_users": 0,
            "total_watch_time_hours": 0,
            "completion_rate": 0.0,
            "transcode_rate": 0.0
        }