"""
Server management endpoints with input validation
Example of how to apply validators to existing routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from ....core.database import get_db
from ....core.security import get_current_admin_user, get_current_admin_or_local_user
from ....models.user import User
from ....schemas.server import ServerResponse
from ....services.server_service import ServerService
from ....services.audit_service import AuditService
from ....providers.factory import ProviderFactory
from ....models.server import Server, ServerType

# Import validators
from ...validators import (
    ServerCreateValidator,
    ServerUpdateValidator,
    validate_input
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/servers", response_model=ServerResponse)
async def create_server(
    server_data: ServerCreateValidator,  # Use validator instead of raw schema
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new media server with validated input"""
    server_service = ServerService(db)

    # The data is already validated by Pydantic
    # Test connection before saving
    if server_data.credentials:
        temp_server = Server(
            name=server_data.name,
            type=ServerType[server_data.type],
            base_url=str(server_data.base_url),
            owner_id=current_user.id
        )

        # Create provider using factory
        logger.debug(f"Creating provider for {server_data.type} with validated credentials")
        provider = ProviderFactory.create_provider(temp_server, credentials=server_data.credentials)

        if not await provider.connect():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to server with provided credentials"
            )

    # Convert validator model to service schema
    server_create_data = {
        "name": server_data.name,
        "type": server_data.type,
        "base_url": str(server_data.base_url),
        "credentials": server_data.credentials
    }

    server = server_service.create_server(current_user.id, server_create_data)

    # Log the action
    AuditService.log_server_created(db, current_user, server.name, request)

    return ServerResponse.from_orm(server)


@router.put("/servers/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdateValidator,  # Use validator
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update server configuration with validated input"""
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
            # Create temporary server object with potential new values
            temp_server = Server(
                id=server.id,
                name=server_data.name or server.name,
                type=ServerType[server_data.type] if server_data.type else server.type,
                base_url=str(server_data.base_url) if server_data.base_url else server.base_url,
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

    # Convert validator model to update data
    update_data = {}
    if server_data.name is not None:
        update_data["name"] = server_data.name
    if server_data.type is not None:
        update_data["type"] = server_data.type
    if server_data.base_url is not None:
        update_data["base_url"] = str(server_data.base_url)
    if server_data.enabled is not None:
        update_data["enabled"] = server_data.enabled
    if server_data.credentials is not None:
        update_data["credentials"] = server_data.credentials

    updated_server = server_service.update_server(server_id, update_data)
    return ServerResponse.from_orm(updated_server)


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get all servers accessible by the user"""
    server_service = ServerService(db)

    # Admin users see all their servers
    if current_user.type.value in ["admin", "staff", "support"]:
        servers = server_service.get_servers_by_owner(current_user.id)
    else:
        # Local users only see servers they have permission for
        from ....models.permissions import UserPermission
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
    """Get server details with validation"""
    # Validate server_id
    if server_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid server ID"
        )

    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions
    if current_user.type.value in ["admin", "staff", "support"]:
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this server"
            )
    else:
        # Local users need specific permission
        from ....models.permissions import UserPermission
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


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a server with validation"""
    # Validate server_id
    if server_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid server ID"
        )

    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Log the action before deletion
    AuditService.log_server_deleted(db, current_user, server.name, request)

    server_service.delete_server(server_id)
    return {"message": "Server deleted successfully"}