"""
Proxmox integration endpoints
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from time import time

from ....core.database import get_db
from ....core.security import get_current_admin_user
from ....models.user import User
from ....models.settings import ProxmoxIntegration
from ....models.server import Server
from ....services.proxmox_service import ProxmoxService
from ....services.audit_service import AuditService

router = APIRouter()

# Simple in-memory cache for metrics (1 second TTL)
metrics_cache = {}
CACHE_TTL = 1


class ProxmoxAuthRequest(BaseModel):
    host: str
    api_token: str
    node: Optional[str] = "pve"
    port: Optional[int] = 8006
    verify_ssl: Optional[bool] = False


class ProxmoxContainerMapping(BaseModel):
    server_id: int
    node: str
    vmid: int
    container_name: str


@router.post("/proxmox/auth")
async def authenticate_proxmox(
    auth_data: ProxmoxAuthRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Test Proxmox connection and save integration settings"""
    async with ProxmoxService(db) as service:
        # Test connection
        test_result = await service.test_connection(
            auth_data.host,
            auth_data.api_token,
            auth_data.verify_ssl
        )

        if not test_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=test_result.get("message", "Connection test failed")
            )

        # Get or create integration
        integration = db.query(ProxmoxIntegration).first()

        if not integration:
            integration = ProxmoxIntegration(
                name="Proxmox",
                created_by_id=current_user.id
            )
            db.add(integration)
        else:
            # Update the created_by_id to track who last configured it
            integration.created_by_id = current_user.id

        # Update settings
        integration.host = auth_data.host
        integration.port = auth_data.port
        integration.node = auth_data.node
        integration.api_token = auth_data.api_token  # TODO: Encrypt in production
        integration.verify_ssl = auth_data.verify_ssl
        integration.enabled = True
        integration.updated_at = datetime.utcnow()

        # Get and cache containers
        containers = await service.get_all_lxc_containers(
            auth_data.host,
            auth_data.api_token,
            auth_data.verify_ssl
        )
        integration.cached_containers = containers
        integration.containers_updated_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": test_result.get("message", "Connected to Proxmox successfully"),
            "version": test_result.get("version"),
            "containers": containers
        }


@router.get("/proxmox/status")
async def get_proxmox_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get Proxmox integration status"""
    import logging
    logger = logging.getLogger(__name__)

    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if not integration:
        return {
            "connected": False,
            "message": "Proxmox not configured"
        }

    # Test connection
    is_connected = False
    connection_error = None

    async with ProxmoxService(db) as service:
        try:
            test_result = await service.test_connection(
                integration.host,
                integration.api_token,
                integration.verify_ssl
            )
            is_connected = test_result.get("success", False)
            if not is_connected:
                logger.warning(f"Proxmox connection test failed for {integration.host}")
                connection_error = test_result.get("message")
        except Exception as e:
            logger.error(f"Proxmox connection test error: {str(e)}")
            connection_error = str(e)
            is_connected = False

    return {
        "connected": is_connected,
        "enabled": integration.enabled,
        "host": integration.host,
        "port": integration.port,
        "node": integration.node,
        "verify_ssl": integration.verify_ssl,
        "container_mappings": integration.container_mappings or {},
        "containers_count": len(integration.cached_containers or []),
        "updated_at": integration.updated_at.isoformat() if integration.updated_at else None,
        "connection_error": connection_error
    }


@router.get("/proxmox/containers")
async def get_proxmox_containers(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get list of LXC containers from Proxmox"""
    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox integration not configured"
        )

    async with ProxmoxService(db) as service:
        containers = await service.get_all_lxc_containers(
            integration.host,
            integration.api_token,
            integration.verify_ssl
        )

        # Update cached containers
        integration.cached_containers = containers
        integration.containers_updated_at = datetime.utcnow()
        db.commit()

        return containers


@router.post("/proxmox/container-mapping")
async def set_container_mapping(
    mapping: ProxmoxContainerMapping,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Map a media server to an LXC container"""
    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox integration not configured"
        )

    # Update container mappings
    if not integration.container_mappings:
        integration.container_mappings = {}

    mappings = dict(integration.container_mappings)
    mappings[str(mapping.server_id)] = {
        "node": mapping.node,
        "vmid": mapping.vmid,
        "container_name": mapping.container_name
    }
    integration.container_mappings = mappings

    db.commit()

    return {"success": True, "mappings": integration.container_mappings}


@router.get("/proxmox/metrics/{server_id}")
async def get_proxmox_metrics(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get real-time LXC container metrics from Proxmox with caching"""
    # Check cache first
    cache_key = f"{current_user.id}_{server_id}"
    if cache_key in metrics_cache:
        cached_data, timestamp = metrics_cache[cache_key]
        if time() - timestamp < CACHE_TTL:
            return cached_data

    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox integration not configured"
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

    node = server_mapping.get("node")
    vmid = server_mapping.get("vmid")
    container_name = server_mapping.get("container_name")

    async with ProxmoxService(db) as service:
        stats = await service.get_container_stats(
            integration.host,
            node,
            vmid,
            integration.api_token,
            integration.verify_ssl
        )

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
            "memory_used_gb": stats.get("memory_used_gb", 0),
            "memory_total_gb": stats.get("memory_total_gb", 0),
            "container": container_name,
            "status": stats.get("status"),
            "timestamp": stats.get("timestamp"),
            "gpu": {"available": False}
        }

        # Cache the result
        metrics_cache[cache_key] = (result, time())

        return result


@router.post("/proxmox/container/{server_id}/action")
async def container_action(
    server_id: int,
    action: str,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Perform an action on a server's LXC container (start, stop, shutdown, reboot)"""
    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if not integration or not integration.api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox integration not configured"
        )

    # Get container mapping for this server
    mappings = integration.container_mappings or {}
    server_mapping = mappings.get(str(server_id))

    if not server_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No container mapped for this server"
        )

    node = server_mapping.get("node")
    vmid = server_mapping.get("vmid")

    async with ProxmoxService(db) as service:
        result = await service.container_action(
            integration.host,
            node,
            vmid,
            action,
            integration.api_token,
            integration.verify_ssl
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Action failed")
            )

        # Get server info for audit log
        server = db.query(Server).filter(Server.id == server_id).first()
        server_name = server.name if server else f"Server {server_id}"
        container_name = server_mapping.get("container_name", f"{node}:{vmid}")

        # Log container action
        AuditService.log_container_action(
            db, current_user, action, server_id, server_name, container_name, request
        )

        return result


@router.delete("/proxmox/disconnect")
async def disconnect_proxmox(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Disconnect Proxmox integration"""
    integration = db.query(ProxmoxIntegration).filter_by(enabled=True).first()

    if integration:
        db.delete(integration)
        db.commit()

    return {"success": True}
