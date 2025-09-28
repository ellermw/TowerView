from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.database import get_db
from ...core.security import get_current_admin_user, get_current_admin_or_local_user
from ...models.user import User
from ...models.settings import NetdataIntegration, SystemSettings, PortainerIntegration
from ...services.netdata_cloud_service import NetdataCloudService
from ...services.portainer_service import PortainerService
from ...services.audit_service import AuditService
import asyncio
import json

router = APIRouter()

class SiteSettingsRequest(BaseModel):
    site_name: str


class NetdataAuthRequest(BaseModel):
    api_token: str
    space_id: Optional[str] = None


class NetdataNodeMapping(BaseModel):
    server_id: int
    node_id: str
    node_name: str
    container_name: Optional[str] = None


class NetdataIntegrationResponse(BaseModel):
    id: int
    enabled: bool
    has_token: bool
    space_id: Optional[str]
    node_mappings: Dict[str, Any]  # Changed from Dict[str, str] to Dict[str, Any]
    cached_nodes: List[Dict[str, Any]]
    nodes_updated_at: Optional[str]

    class Config:
        from_attributes = True


@router.post("/netdata/auth")
async def authenticate_netdata(
    auth_data: NetdataAuthRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Authenticate with Netdata Cloud and save credentials"""
    # Clean the token of any whitespace and line breaks
    import re
    token = re.sub(r'\s+', '', auth_data.api_token)

    async with NetdataCloudService(db) as service:
        # Test the connection
        if not await service.test_connection(token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API token or unable to connect to Netdata Cloud"
            )

        # Get spaces if not provided
        spaces = []
        if not auth_data.space_id:
            spaces = await service.get_spaces(token)
            if not spaces:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No spaces found in your Netdata Cloud account"
                )
            # Use first space by default
            auth_data.space_id = spaces[0]["id"] if isinstance(spaces[0], dict) else spaces[0]

        # Save the integration
        if not await service.save_integration(current_user.id, token, auth_data.space_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save integration settings"
            )

        # Get nodes for the space
        nodes = await service.get_nodes(token, auth_data.space_id)

        return {
            "success": True,
            "spaces": spaces,
            "selected_space_id": auth_data.space_id,
            "nodes": nodes
        }


@router.get("/netdata/status", response_model=NetdataIntegrationResponse)
async def get_netdata_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get Netdata integration status"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration:
        return NetdataIntegrationResponse(
            id=0,
            enabled=False,
            has_token=False,
            space_id=None,
            node_mappings={},
            cached_nodes=[],
            nodes_updated_at=None
        )

    return NetdataIntegrationResponse(
        id=integration.id,
        enabled=integration.enabled,
        has_token=bool(integration.api_token),
        space_id=integration.space_id,
        node_mappings=integration.node_mappings or {},
        cached_nodes=integration.cached_nodes or [],
        nodes_updated_at=integration.nodes_updated_at.isoformat() if integration.nodes_updated_at else None
    )


@router.get("/netdata/nodes")
async def get_netdata_nodes(
    refresh: bool = False,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get available Netdata nodes"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Netdata integration not configured"
        )

    # Return cached nodes if not refreshing and cache is recent (< 5 minutes old)
    if not refresh and integration.cached_nodes and integration.nodes_updated_at:
        from datetime import datetime, timedelta
        if datetime.utcnow() - integration.nodes_updated_at < timedelta(minutes=5):
            return integration.cached_nodes

    # Fetch fresh nodes
    async with NetdataCloudService(db) as service:
        nodes = await service.get_nodes(integration.api_token, integration.space_id)

        # Update cache
        integration.cached_nodes = nodes
        integration.nodes_updated_at = datetime.utcnow()
        db.commit()

        return nodes


@router.post("/netdata/node-mapping")
async def set_node_mapping(
    mapping: NetdataNodeMapping,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Map a Netdata node to a media server"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Netdata integration not configured"
        )

    # Update node mappings
    if not integration.node_mappings:
        integration.node_mappings = {}

    mappings = dict(integration.node_mappings)
    mappings[str(mapping.server_id)] = {
        "node_id": mapping.node_id,
        "node_name": mapping.node_name,
        "container_name": mapping.container_name
    }
    integration.node_mappings = mappings

    db.commit()

    return {"success": True, "mappings": integration.node_mappings}


@router.delete("/netdata/node-mapping/{server_id}")
async def delete_node_mapping(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Remove a Netdata node mapping"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration or not integration.node_mappings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mappings found"
        )

    mappings = dict(integration.node_mappings)
    if str(server_id) in mappings:
        del mappings[str(server_id)]
        integration.node_mappings = mappings
        db.commit()

    return {"success": True}


@router.get("/netdata/containers/{node_id}")
async def get_node_containers(
    node_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get Docker containers on a Netdata node"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Netdata integration not configured"
        )

    async with NetdataCloudService(db) as service:
        containers = await service.get_docker_containers(integration.api_token, integration.space_id, node_id)
        return containers


@router.get("/netdata/metrics/{server_id}")
async def get_server_metrics(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get real-time metrics for a server from Netdata"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Netdata integration not configured"
        )

    # Get node mapping for this server
    mappings = integration.node_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        # Return empty metrics if no mapping
        return {
            "mapped": False,
            "metrics": {}
        }

    node_id = server_mapping.get("node_id")
    container_name = server_mapping.get("container_name")

    async with NetdataCloudService(db) as service:
        # If a specific container is mapped, get container metrics
        if container_name:
            container_metrics = await service.get_container_metrics(
                integration.api_token, integration.space_id, node_id, container_name
            )

            # Also get GPU metrics for the host (containers share GPU)
            gpu_metrics = await service.get_gpu_metrics(
                integration.api_token, integration.space_id, node_id
            )

            # Format container metrics to match system metrics structure
            system_metrics = {
                "cpu_usage": container_metrics.get("cpu_usage", 0),
                "memory_usage": container_metrics.get("memory_usage", 0),
                "memory_used_gb": container_metrics.get("memory_used_mb", 0) / 1024,
                "memory_total_gb": container_metrics.get("memory_limit_mb", 0) / 1024,
                "container": container_name,
                "timestamp": container_metrics.get("timestamp")
            }
        else:
            # Fetch host system and GPU metrics
            system_metrics, gpu_metrics = await asyncio.gather(
                service.get_system_metrics(integration.api_token, integration.space_id, node_id),
                service.get_gpu_metrics(integration.api_token, integration.space_id, node_id)
            )

        return {
            "mapped": True,
            "node_name": server_mapping.get("node_name"),
            "container_name": container_name,
            "system": system_metrics,
            "gpu": gpu_metrics
        }


@router.delete("/netdata/disconnect")
async def disconnect_netdata(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Disconnect Netdata integration"""
    integration = db.query(NetdataIntegration).filter_by(created_by_id=current_user.id).first()

    if integration:
        db.delete(integration)
        db.commit()

    return {"success": True}


# Portainer Integration endpoints

class PortainerAuthRequest(BaseModel):
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    api_token: Optional[str] = None
    endpoint_id: Optional[int] = 1


class PortainerContainerMapping(BaseModel):
    server_id: int
    container_id: str
    container_name: str


@router.post("/portainer/auth")
async def authenticate_portainer(
    auth_data: PortainerAuthRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Authenticate with Portainer and save integration settings"""
    async with PortainerService(db) as service:
        # Ensure URL has protocol
        url = auth_data.url
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        # Check if we have an API token directly or need to authenticate
        if auth_data.api_token:
            # Use provided API token directly
            token = auth_data.api_token
            # Test the token
            containers = await service.get_containers(url, token, auth_data.endpoint_id)
            if containers is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid API token or unable to connect to Portainer"
                )
        elif auth_data.username and auth_data.password:
            # Authenticate with username/password to get JWT token
            auth_result = await service.authenticate(url, auth_data.username, auth_data.password)

            if not auth_result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=auth_result.get("message", "Authentication failed")
                )

            token = auth_result.get("jwt")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either API token or username/password required"
            )

        # Save integration settings
        success = await service.save_integration(
            current_user.id, url, token, auth_data.endpoint_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save integration settings"
            )

        # Get containers list
        containers = await service.get_containers(url, token, auth_data.endpoint_id)

        return {
            "success": True,
            "message": "Successfully connected to Portainer",
            "containers": containers
        }


@router.get("/portainer/status")
async def get_portainer_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get Portainer integration status"""
    # Look for any enabled Portainer integration (global)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration:
        return {
            "connected": False,
            "message": "Portainer not configured"
        }

    # Test connection
    async with PortainerService(db) as service:
        is_connected = await service.test_connection(integration.url, integration.api_token)

    return {
        "connected": is_connected,
        "enabled": integration.enabled,
        "url": integration.url,
        "endpoint_id": integration.endpoint_id,
        "container_mappings": integration.container_mappings or {},
        "containers_count": len(integration.cached_containers or []),
        "updated_at": integration.updated_at.isoformat() if integration.updated_at else None
    }


@router.get("/portainer/containers")
async def get_portainer_containers(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get list of Docker containers from Portainer"""
    # Look for any enabled Portainer integration (global)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    async with PortainerService(db) as service:
        containers = await service.get_containers(
            integration.url, integration.api_token, integration.endpoint_id
        )

        # Update cached containers
        from datetime import datetime
        integration.cached_containers = containers
        integration.containers_updated_at = datetime.utcnow()
        db.commit()

        return containers


@router.post("/portainer/container-mapping")
async def set_container_mapping(
    mapping: PortainerContainerMapping,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Map a Docker container to a media server"""
    # Look for any enabled Portainer integration (global)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Update container mappings
    if not integration.container_mappings:
        integration.container_mappings = {}

    mappings = dict(integration.container_mappings)
    mappings[str(mapping.server_id)] = {
        "container_id": mapping.container_id,
        "container_name": mapping.container_name
    }
    integration.container_mappings = mappings

    db.commit()

    return {"success": True, "mappings": integration.container_mappings}


from functools import lru_cache
from time import time

# Simple in-memory cache for metrics (1 second TTL)
metrics_cache = {}
CACHE_TTL = 1  # 1 second cache to handle rapid requests

@router.get("/portainer/metrics/{server_id}")
async def get_portainer_metrics(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get real-time container metrics from Portainer with caching"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to view this server"
            )

    # Check cache first
    cache_key = f"{current_user.id}_{server_id}"
    if cache_key in metrics_cache:
        cached_data, timestamp = metrics_cache[cache_key]
        if time() - timestamp < CACHE_TTL:
            return cached_data

    # Get the Portainer integration (there's only one global integration)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "memory_used_gb": 0,
            "memory_total_gb": 0,
            "container": None
        }

    container_id = server_mapping.get("container_id")
    container_name = server_mapping.get("container_name")

    async with PortainerService(db) as service:
        # Get container stats and GPU stats in parallel
        import asyncio
        stats_task = service.get_container_stats(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )
        gpu_task = service.get_gpu_stats(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        stats, gpu_stats = await asyncio.gather(stats_task, gpu_task)

        if not stats:
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "container": container_name,
                "gpu": {"available": False}
            }

        result = {
            "cpu_usage": stats.get("cpu_percent", 0),
            "memory_usage": stats.get("memory_percent", 0),
            "memory_used_gb": stats.get("memory_usage_mb", 0) / 1024,
            "memory_total_gb": stats.get("memory_limit_mb", 0) / 1024,
            "container": container_name,
            "timestamp": stats.get("timestamp"),
            "gpu": gpu_stats
        }

        # Cache the result
        metrics_cache[cache_key] = (result, time())

        return result


@router.post("/portainer/container/{server_id}/action")
async def container_action(
    server_id: int,
    action: str,
    request: Request,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Perform an action on a server's container (start, stop, restart)"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id,
            UserPermission.can_manage_server == True
        ).first()

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to manage this server"
            )

    # Get the global Portainer integration (not user-specific anymore)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        result = await service.container_action(
            integration.url, integration.api_token, container_id, action, integration.endpoint_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Action failed")
            )

        # Get server info for audit log
        from ...models.server import Server
        server = db.query(Server).filter(Server.id == server_id).first()
        server_name = server.name if server else f"Server {server_id}"
        container_name = server_mapping.get("container_name", container_id)

        # Log container action
        AuditService.log_container_action(
            db, current_user, action, server_id, server_name, container_name, request
        )

        return result


@router.get("/portainer/container/{server_id}/info")
async def get_container_info(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a server's container"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check permissions for local users - need manage permission for container info
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id,
            UserPermission.can_manage_server == True
        ).first()
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to manage this server"
            )

    # Get the global Portainer integration
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        return {"mapped": False}

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        info = await service.get_container_info(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        return {
            "mapped": True,
            "container_name": server_mapping.get("container_name"),
            **info
        }


@router.post("/portainer/container/{server_id}/start")
async def start_container(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Start a Docker container for a server"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission
    from ...models.server import Server

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_server:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to manage this server"
            )

    # Get the global Portainer integration (not user-specific)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        result = await service.start_container(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to start container")
            )

        return result


@router.post("/portainer/container/{server_id}/stop")
async def stop_container(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Stop a Docker container for a server"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_server:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to manage this server"
            )

    # Get the global Portainer integration
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        result = await service.stop_container(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to stop container")
            )

        return result


@router.post("/portainer/container/{server_id}/update")
async def update_container(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),  # Admin only for updates
    db: Session = Depends(get_db)
):
    """Update a Docker container by recreating it with latest image"""
    from ...models.server import Server

    # Get the global Portainer integration
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        result = await service.recreate_container(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        if result.get("success"):
            # Update the container mapping with new container ID
            new_container_id = result.get("new_container_id")
            if new_container_id:
                # Update the container ID in the mapping
                mappings[str(server_id)]["container_id"] = new_container_id[:12]  # Store short ID
                integration.container_mappings = mappings
                db.commit()

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to update container")
            )

        return result


@router.post("/portainer/container/{server_id}/restart")
async def restart_container(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Restart a Docker container for a server"""
    from ...models.user import UserType
    from ...models.user_permission import UserPermission

    # Check permissions for local users
    if current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_server:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to manage this server"
            )

    # Get the global Portainer integration
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portainer integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    container_id = server_mapping.get("container_id")

    async with PortainerService(db) as service:
        result = await service.restart_container(
            integration.url, integration.api_token, container_id, integration.endpoint_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to restart container")
            )

        return result


@router.delete("/portainer/disconnect")
async def disconnect_portainer(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Disconnect Portainer integration"""
    # Look for any enabled Portainer integration (global)
    integration = db.query(PortainerIntegration).filter_by(enabled=True).first()

    if integration:
        db.delete(integration)
        db.commit()

    return {"success": True}


# Site Settings endpoints

@router.get("/site")
async def get_site_settings(
    db: Session = Depends(get_db)
):
    """Get site-wide settings including site name"""
    # Get site name setting
    site_name_setting = db.query(SystemSettings).filter_by(key="site_name").first()

    return {
        "site_name": site_name_setting.value if site_name_setting else "The Tower - View"
    }


@router.post("/site")
async def update_site_settings(
    settings: SiteSettingsRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update site-wide settings (admin only)"""
    # Update or create site name setting
    site_name_setting = db.query(SystemSettings).filter_by(key="site_name").first()

    if not site_name_setting:
        site_name_setting = SystemSettings(
            key="site_name",
            value=settings.site_name,
            category="general",
            description="The display name of the application",
            updated_by_id=current_user.id
        )
        db.add(site_name_setting)
    else:
        site_name_setting.value = settings.site_name
        site_name_setting.updated_by_id = current_user.id

    db.commit()

    return {"success": True, "site_name": settings.site_name}