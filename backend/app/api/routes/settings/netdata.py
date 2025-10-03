"""
Netdata integration endpoints
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import re

from ....core.database import get_db
from ....core.security import get_current_admin_user
from ....models.user import User
from ....models.settings import NetdataIntegration
from ....services.netdata_cloud_service import NetdataCloudService

router = APIRouter()


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
    node_mappings: Dict[str, Any]
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