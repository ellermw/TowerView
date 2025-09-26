from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_admin_user, get_current_admin_or_local_user
from ...models.user import User, UserType
from ...models.server import Server
from ...schemas.server import ServerCreate, ServerResponse, ServerUpdate
from ...schemas.session import SessionResponse, LiveSessionResponse
from ...schemas.user import (
    UserResponse, ServerUserResponse, LocalUserCreate,
    LocalUserUpdate, LocalUserResponse, UserPermissionSchema,
    UserPermissionUpdate
)
from ...schemas.analytics import AnalyticsFilters, DashboardAnalyticsResponse
from ...services.server_service import ServerService
from ...services.analytics_service import AnalyticsService
from ...services.audit_service import AuditService
from ...providers.factory import ProviderFactory
from ...models.playback_analytics import PlaybackEvent
from datetime import datetime
from typing import Dict, Any

router = APIRouter()


@router.post("/servers", response_model=ServerResponse)
async def create_server(
    server_data: ServerCreate,
    request: Request,
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

    # Log server creation
    AuditService.log_server_action(
        db, current_user, "add", server.id, server.name, server.type.value, request
    )

    return ServerResponse.from_orm(server)


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """List all servers accessible by the current user"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    server_service = ServerService(db)

    if current_user.type == UserType.admin:
        # Admins see all servers they own
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users see servers they have permissions for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id
        ).all()
        server_ids = [perm.server_id for perm in permissions]
        if server_ids:
            servers = db.query(Server).filter(Server.id.in_(server_ids)).all()
        else:
            servers = []

    return [ServerResponse.from_orm(server) for server in servers]


@router.get("/servers/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get server details"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check access
    if current_user.type == UserType.admin:
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
    else:
        # Local user - check permissions
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()
        if not permission:
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
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get active sessions from all servers accessible by the user"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    server_service = ServerService(db)

    # Get servers based on user type
    if current_user.type == UserType.admin:
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users see servers they have permission to view sessions for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_sessions == True
        ).all()
        server_ids = [perm.server_id for perm in permissions]
        if server_ids:
            servers = db.query(Server).filter(Server.id.in_(server_ids)).all()
        else:
            servers = []

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


@router.get("/servers/{server_id}/version")
async def get_server_version(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get server version information"""
    from ...providers.factory import ProviderFactory

    # Get the server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        from ...models.user_permission import UserPermission
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to view this server"
            )

    try:
        # Create provider and get version info
        provider = ProviderFactory.create_provider(server, db)
        version_info = await provider.get_version_info()
        return version_info
    except Exception as e:
        logger.error(f"Error getting version info for server {server.name}: {e}")
        # Return empty version info instead of error to prevent UI issues
        return {
            "current_version": "Unknown",
            "latest_version": "Unknown",
            "update_available": False
        }


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


@router.get("/gpu-status")
async def get_gpu_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get GPU utilization status across all servers"""
    server_service = ServerService(db)
    servers = server_service.get_servers_by_owner(current_user.id)

    gpu_status = {
        "total_hw_transcodes": 0,
        "total_sw_transcodes": 0,
        "total_transcodes": 0,
        "servers": []
    }

    for server in servers:
        try:
            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()

            server_hw_transcodes = 0
            server_sw_transcodes = 0
            hw_sessions = []
            sw_sessions = []

            for session in sessions:
                if session.get("video_decision") == "transcode":
                    is_hw = (
                        session.get("transcode_hw_full_pipeline") or
                        (session.get("transcode_hw_decode") and session.get("transcode_hw_encode"))
                    )

                    if is_hw:
                        server_hw_transcodes += 1
                        hw_sessions.append({
                            "session_id": session.get("session_id"),
                            "username": session.get("username"),
                            "title": session.get("title") or session.get("full_title"),
                            "decode": session.get("transcode_hw_decode_title") or ("Hardware" if session.get("transcode_hw_decode") else "Software"),
                            "encode": session.get("transcode_hw_encode_title") or ("Hardware" if session.get("transcode_hw_encode") else "Software"),
                            "speed": session.get("transcode_speed"),
                            "throttled": session.get("transcode_throttled", False)
                        })
                    else:
                        server_sw_transcodes += 1
                        sw_sessions.append({
                            "session_id": session.get("session_id"),
                            "username": session.get("username"),
                            "title": session.get("title") or session.get("full_title"),
                            "speed": session.get("transcode_speed"),
                            "throttled": session.get("transcode_throttled", False)
                        })

            if server_hw_transcodes > 0 or server_sw_transcodes > 0:
                gpu_status["servers"].append({
                    "server_id": server.id,
                    "server_name": server.name,
                    "server_type": server.type.value,
                    "hw_transcodes": server_hw_transcodes,
                    "sw_transcodes": server_sw_transcodes,
                    "hw_sessions": hw_sessions,
                    "sw_sessions": sw_sessions
                })

                gpu_status["total_hw_transcodes"] += server_hw_transcodes
                gpu_status["total_sw_transcodes"] += server_sw_transcodes

        except Exception as e:
            print(f"Failed to get GPU status from server {server.name}: {e}")
            continue

    gpu_status["total_transcodes"] = gpu_status["total_hw_transcodes"] + gpu_status["total_sw_transcodes"]
    gpu_status["hw_percentage"] = (
        round((gpu_status["total_hw_transcodes"] / gpu_status["total_transcodes"]) * 100, 1)
        if gpu_status["total_transcodes"] > 0 else 0
    )

    return gpu_status


@router.post("/servers/{server_id}/sessions/{session_id}/terminate")
async def terminate_session(
    server_id: int,
    session_id: str,
    request: Request,
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

        # Get session info for audit log (if available)
        session_info = "Session"
        try:
            sessions = await provider.get_current_sessions()
            for session in sessions:
                if session.get("Id") == session_id or session.get("session_id") == session_id:
                    username = session.get("UserName", session.get("username", "Unknown"))
                    session_info = username
                    break
        except:
            pass

        # Log the action
        AuditService.log_session_terminated(
            db, current_user, session_id, session_info, server.name, request
        )

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
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get users from all servers"""
    from ...models.user_permission import UserPermission

    server_service = ServerService(db)

    # Get servers based on user type
    if current_user.type == UserType.admin:
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users - get servers they have view_users permission for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_users == True
        ).all()
        server_ids = [perm.server_id for perm in permissions]
        if server_ids:
            servers = db.query(Server).filter(Server.id.in_(server_ids)).all()
        else:
            servers = []

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


@router.get("/bandwidth")
async def get_bandwidth_history(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get cached bandwidth history data"""
    from datetime import datetime, timedelta

    # Get bandwidth history from cache (last 5 minutes)
    from ...services.bandwidth_cache import get_bandwidth_history

    bandwidth_data = await get_bandwidth_history()
    return bandwidth_data


@router.post("/analytics")
async def get_analytics(
    filters: AnalyticsFilters,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get analytics data for dashboard"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission
    from ...services.analytics_service import AnalyticsService

    # Filter servers based on user permissions
    if current_user.type == UserType.local_user:
        # Get servers the local user has analytics permissions for
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_analytics == True
        ).all()
        allowed_server_ids = [perm.server_id for perm in permissions]

        # Apply server filter to analytics
        if filters.server_id:
            # Check if requested server is allowed
            if filters.server_id not in allowed_server_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permission to view analytics for this server"
                )
        # Note: if server_id is None, the analytics service will use all servers
        # which we'll need to filter in the service itself

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


# Local User Management Endpoints

@router.get("/local-users", response_model=List[LocalUserResponse])
async def get_local_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all local users"""
    from ...models.user import UserType
    users = db.query(User).filter(User.type == UserType.local_user).all()
    return users


@router.post("/local-users", response_model=LocalUserResponse)
async def create_local_user(
    user_data: LocalUserCreate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new local user"""
    from ...models.user import UserType
    from ...core.security import get_password_hash

    # Check if username already exists (case-insensitive)
    from sqlalchemy import func
    existing_user = db.query(User).filter(func.lower(User.username) == user_data.username.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Create new local user
    new_user = User(
        type=UserType.local_user,
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        must_change_password=user_data.must_change_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Log user creation
    AuditService.log_user_created(
        db, current_user, new_user.id, new_user.username, "local_user", request
    )

    return new_user


@router.get("/local-users/{user_id}", response_model=LocalUserResponse)
async def get_local_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get a specific local user"""
    from ...models.user import UserType

    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.patch("/local-users/{user_id}", response_model=LocalUserResponse)
async def update_local_user(
    user_id: int,
    user_data: LocalUserUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update a local user"""
    from ...models.user import UserType
    from ...core.security import get_password_hash

    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Track changes for audit log
    changes = {}
    if user_data.email is not None and user_data.email != user.email:
        changes["email"] = {"old": user.email, "new": user_data.email}
        user.email = user_data.email
    if user_data.password is not None:
        changes["password"] = "changed"
        user.password_hash = get_password_hash(user_data.password)
    if user_data.must_change_password is not None and user_data.must_change_password != user.must_change_password:
        changes["must_change_password"] = {"old": user.must_change_password, "new": user_data.must_change_password}
        user.must_change_password = user_data.must_change_password

    db.commit()
    db.refresh(user)

    # Log user modification if there were changes
    if changes:
        AuditService.log_user_modified(
            db, current_user, user.id, user.username, changes, request
        )

    return user


@router.delete("/local-users/{user_id}")
async def delete_local_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a local user"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission
    from ...models.session import Session
    from ...models.playback_analytics import PlaybackEvent

    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Store username before deletion
    username = user.username
    user_type = user.type.value if hasattr(user.type, 'value') else str(user.type)

    # Delete related records first to avoid foreign key constraints
    # Delete user permissions
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()

    # Delete or update sessions
    db.query(Session).filter(Session.user_id == user_id).update({"user_id": None})

    # Delete or update playback events
    db.query(PlaybackEvent).filter(PlaybackEvent.user_id == user_id).update({"user_id": None})

    # Now delete the user
    db.delete(user)
    db.commit()

    # Log user deletion
    AuditService.log_user_deleted(
        db, current_user, username, user_type, request
    )

    return {"message": "User deleted successfully"}


# User Permission Endpoints

@router.get("/local-users/{user_id}/permissions", response_model=List[UserPermissionSchema])
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),  # Allow local users to fetch their own
    db: Session = Depends(get_db)
):
    """Get permissions for a local user"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check authorization: users can fetch their own permissions, admins can fetch anyone's
    if current_user.id != user_id and current_user.type != UserType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these permissions"
        )

    permissions = db.query(UserPermission).filter(
        UserPermission.user_id == user_id
    ).all()

    return permissions


@router.post("/local-users/{user_id}/permissions", response_model=UserPermissionSchema)
async def grant_user_permission(
    user_id: int,
    permission_data: UserPermissionSchema,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Grant permissions to a local user for a server"""
    from ...models.user_permission import UserPermission
    from ...models.user import UserType

    # Check if user exists and is a local user
    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not a local user"
        )

    # Check if server exists
    server = db.query(Server).filter(Server.id == permission_data.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check if permission already exists
    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == permission_data.server_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already exists for this user and server"
        )

    # Create new permission
    permission = UserPermission(
        user_id=user_id,
        server_id=permission_data.server_id,
        can_view_sessions=permission_data.can_view_sessions,
        can_view_users=permission_data.can_view_users,
        can_view_analytics=permission_data.can_view_analytics,
        can_terminate_sessions=permission_data.can_terminate_sessions,
        can_manage_server=permission_data.can_manage_server
    )

    db.add(permission)
    db.commit()
    db.refresh(permission)

    return permission


@router.patch("/local-users/{user_id}/permissions/{server_id}", response_model=UserPermissionSchema)
async def update_user_permission(
    user_id: int,
    server_id: int,
    permission_data: UserPermissionUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user permissions for a server"""
    from ...models.user_permission import UserPermission

    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == server_id
    ).first()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    # Update fields if provided
    if permission_data.can_view_sessions is not None:
        permission.can_view_sessions = permission_data.can_view_sessions
    if permission_data.can_view_users is not None:
        permission.can_view_users = permission_data.can_view_users
    if permission_data.can_view_analytics is not None:
        permission.can_view_analytics = permission_data.can_view_analytics
    if permission_data.can_terminate_sessions is not None:
        permission.can_terminate_sessions = permission_data.can_terminate_sessions
    if permission_data.can_manage_server is not None:
        permission.can_manage_server = permission_data.can_manage_server

    db.commit()
    db.refresh(permission)

    return permission


@router.delete("/local-users/{user_id}/permissions/{server_id}")
async def revoke_user_permission(
    user_id: int,
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Revoke user permissions for a server"""
    from ...models.user_permission import UserPermission

    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == server_id
    ).first()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    db.delete(permission)
    db.commit()

    return {"message": "Permission revoked successfully"}
# Audit Log endpoints
@router.get("/audit-logs")
async def get_audit_logs(
    page: int = 1,
    per_page: int = 50,
    action: str = None,
    actor_type: str = None,
    search: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get audit logs - admin only"""
    from ...models.audit_log import AuditLog
    from sqlalchemy import desc, or_

    query = db.query(AuditLog)

    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action)
    if actor_type:
        query = query.filter(AuditLog.actor_type == actor_type)
    if search:
        query = query.filter(
            or_(
                AuditLog.actor_username.ilike(f"%{search}%"),
                AuditLog.target_name.ilike(f"%{search}%")
            )
        )
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    # Get total count
    total = query.count()

    # Calculate pagination
    skip = (page - 1) * per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    # Get paginated results
    logs = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(per_page).all()

    return {
        "items": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages
    }


@router.get("/audit-logs/actions")
async def get_audit_log_actions(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get distinct audit log actions for filtering"""
    from ...models.audit_log import AuditLog

    actions = db.query(AuditLog.action).distinct().all()
    return [action[0] for action in actions]
