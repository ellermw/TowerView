"""
Server management endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from ....core.database import get_db
from ....core.security import get_current_admin_user, get_current_admin_or_local_user
from ....models.user import User
from ....schemas.server import ServerCreate, ServerUpdate, ServerResponse
from ....services.server_service import ServerService
from ....services.audit_service import AuditService
from ....providers.factory import ProviderFactory
from ....models.server import Server, ServerType

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/servers", response_model=ServerResponse)
async def create_server(
    server_data: ServerCreate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new media server"""
    server_service = ServerService(db)

    # Test connection before saving
    if server_data.credentials:
        from ....models.server import Server
        temp_server = Server(
            name=server_data.name,
            type=server_data.type,
            base_url=server_data.base_url,
            owner_id=current_user.id
        )
        # Create provider using factory
        logger.debug(f"Creating provider for {server_data.type} with credentials: {list(server_data.credentials.keys()) if server_data.credentials else 'None'}")
        provider = ProviderFactory.create_provider(temp_server, credentials=server_data.credentials)

        if not await provider.connect():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to server with provided credentials"
            )

    server = server_service.create_server(current_user.id, server_data)

    # Log the action
    AuditService.log_server_created(db, current_user, server.name, request)

    return ServerResponse.from_orm(server)


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get all servers accessible by the user"""
    server_service = ServerService(db)

    # Admin users see all servers, staff/support see servers they own
    if current_user.type.value == "admin":
        from ....models.server import Server
        servers = db.query(Server).filter(Server.enabled == True).all()
    elif current_user.type.value in ["staff", "support"]:
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users only see servers they have permission for
        from ....models.user_permission import UserPermission
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            return []

        # Get servers for which user has permissions
        server_ids = [p.server_id for p in permissions]
        from ....models.server import Server
        servers = db.query(Server).filter(
            Server.id.in_(server_ids),
            Server.enabled == True
        ).all()

    return [ServerResponse.from_orm(server) for server in servers]


@router.get("/servers/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get server details"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions
    if current_user.type.value == "admin":
        # Admins can access all servers
        pass
    elif current_user.type.value in ["staff", "support"]:
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this server"
            )
    else:
        # Local users need specific permission
        from ....models.user_permission import UserPermission
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_view_servers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this server"
            )

    return ServerResponse.from_orm(server)


@router.put("/servers/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update server configuration"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions - admins can update any server
    if current_user.type.value != "admin" and server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this server"
        )

    # If credentials are being updated, test the connection
    if server_data.credentials:
        try:
            from ....models.server import Server
            # Create temporary server object with potential new values
            temp_server = Server(
                id=server.id,
                name=server_data.name or server.name,
                type=server_data.type or server.type,
                base_url=server_data.base_url or server.base_url,
                owner_id=current_user.id
            )

            # Create provider with new credentials using factory
            provider = ProviderFactory.create_provider(temp_server, credentials=server_data.credentials)

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
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions - admins can delete any server
    if current_user.type.value != "admin" and server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this server"
        )

    # Log the action before deletion
    AuditService.log_server_deleted(db, current_user, server.name, request)

    server_service.delete_server(server_id)
    return {"message": "Server deleted successfully"}


@router.get("/servers/{server_id}/version")
async def get_server_version(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get server version and update availability"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions (similar to get_server)
    if current_user.type.value == "admin":
        # Admins can access all servers
        pass
    elif current_user.type.value in ["staff", "support"]:
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
    else:
        from ....models.user_permission import UserPermission
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_view_servers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

    try:
        provider = ProviderFactory.create_provider(server, db)
        version_info = await provider.get_version_info()
        return version_info
    except Exception as e:
        logger.error(f"Failed to get version for server {server.name}: {e}")
        return {
            "current_version": "Unknown",
            "latest_version": "Unknown",
            "update_available": False
        }


@router.get("/gpu-status")
async def get_gpu_status(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get GPU transcoding status across all servers"""
    server_service = ServerService(db)

    # Get servers based on user type
    if current_user.type.value in ["admin", "staff", "support"]:
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users - get permitted servers
        from ....models.user_permission import UserPermission
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            return {
                "total_hw_transcodes": 0,
                "total_sw_transcodes": 0,
                "total_transcodes": 0,
                "hw_percentage": 0,
                "servers": []
            }

        server_ids = [p.server_id for p in permissions]
        from ....models.server import Server
        servers = db.query(Server).filter(
            Server.id.in_(server_ids),
            Server.enabled == True
        ).all()

    gpu_status = {
        "total_hw_transcodes": 0,
        "total_sw_transcodes": 0,
        "servers": []
    }

    for server in servers:
        if not server.enabled:
            continue

        try:
            provider = ProviderFactory.create_provider(server, db)
            sessions = await provider.list_active_sessions()

            server_hw_transcodes = 0
            server_sw_transcodes = 0
            hw_sessions = []
            sw_sessions = []

            for session in sessions:
                if session.get("is_transcoding"):
                    if session.get("transcode_hw"):
                        server_hw_transcodes += 1
                        hw_sessions.append({
                            "user": session.get("username", "Unknown"),
                            "title": session.get("title", "Unknown"),
                            "hw_decode": session.get("transcode_hw_decode_title"),
                            "hw_encode": session.get("transcode_hw_encode_title")
                        })
                    else:
                        server_sw_transcodes += 1
                        sw_sessions.append({
                            "user": session.get("username", "Unknown"),
                            "title": session.get("title", "Unknown")
                        })

            if server_hw_transcodes > 0 or server_sw_transcodes > 0:
                gpu_status["servers"].append({
                    "id": server.id,
                    "name": server.name,
                    "type": server.type.value,
                    "hw_transcodes": server_hw_transcodes,
                    "sw_transcodes": server_sw_transcodes,
                    "hw_sessions": hw_sessions,
                    "sw_sessions": sw_sessions
                })

                gpu_status["total_hw_transcodes"] += server_hw_transcodes
                gpu_status["total_sw_transcodes"] += server_sw_transcodes

        except Exception as e:
            logger.error(f"Failed to get GPU status from server {server.name}: {e}")
            continue

    gpu_status["total_transcodes"] = gpu_status["total_hw_transcodes"] + gpu_status["total_sw_transcodes"]
    gpu_status["hw_percentage"] = (
        round((gpu_status["total_hw_transcodes"] / gpu_status["total_transcodes"]) * 100, 1)
        if gpu_status["total_transcodes"] > 0 else 0
    )

    return gpu_status