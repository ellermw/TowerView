from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ...core.database import get_db
from ...core.security import get_current_admin_user, get_current_admin_or_local_user
from ...models.user import User
from ...models.settings import NetdataIntegration, SystemSettings
from ...services.netdata_cloud_service import NetdataCloudService
from ...services.audit_service import AuditService
import asyncio
import json

router = APIRouter()

class SiteSettingsRequest(BaseModel):
    site_name: str

class SyncSettingsRequest(BaseModel):
    # User sync settings
    user_sync_enabled: bool
    user_sync_interval_seconds: int  # Interval in seconds

    # Library sync settings
    library_sync_enabled: bool
    library_sync_interval_seconds: int
    library_passive_discovery: bool  # Always discover from playback_events

    # Cache refresh settings
    sessions_cache_interval_seconds: int
    analytics_cache_interval_seconds: int
    server_status_interval_seconds: int

class SyncSettingsResponse(BaseModel):
    user_sync_enabled: bool
    user_sync_interval_seconds: int
    user_sync_last_run: Optional[datetime]
    user_sync_next_run: Optional[datetime]

    library_sync_enabled: bool
    library_sync_interval_seconds: int
    library_passive_discovery: bool
    library_sync_last_run: Optional[datetime]
    library_sync_next_run: Optional[datetime]

    sessions_cache_interval_seconds: int
    analytics_cache_interval_seconds: int
    server_status_interval_seconds: int


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


# Site Settings endpoints

@router.get("/site")
async def get_site_settings(
    db: Session = Depends(get_db)
):
    """Get site-wide settings"""
    settings = {}

    # Get all site-related settings from system_settings
    site_settings = db.query(SystemSettings).filter(
        SystemSettings.category == "general"
    ).all()

    for setting in site_settings:
        settings[setting.key] = setting.value

    # Default site name if not set
    if "site_name" not in settings:
        settings["site_name"] = "TowerView"

    return settings


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


# Sync Settings endpoints

@router.get("/sync", response_model=SyncSettingsResponse)
async def get_sync_settings(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get sync and cache refresh settings"""
    from datetime import timedelta

    # Default values
    defaults = {
        "user_sync_enabled": False,
        "user_sync_interval_seconds": 3600,  # 1 hour default
        "library_sync_enabled": False,
        "library_sync_interval_seconds": 86400,  # 24 hours default
        "library_passive_discovery": True,
        "sessions_cache_interval_seconds": 30,  # 30 seconds
        "analytics_cache_interval_seconds": 300,  # 5 minutes
        "server_status_interval_seconds": 60,  # 1 minute
    }

    # Get all sync settings
    settings_keys = list(defaults.keys()) + ["user_sync_last_run", "library_sync_last_run"]
    settings_db = db.query(SystemSettings).filter(
        SystemSettings.key.in_(settings_keys)
    ).all()

    # Convert to dict
    settings_dict = {s.key: s.value for s in settings_db}

    # Merge with defaults
    for key, default_value in defaults.items():
        if key not in settings_dict:
            settings_dict[key] = default_value

    # Calculate next run times
    user_sync_next_run = None
    if settings_dict.get("user_sync_enabled"):
        if settings_dict.get("user_sync_last_run"):
            last_run = datetime.fromisoformat(settings_dict["user_sync_last_run"])
            user_sync_next_run = last_run + timedelta(seconds=settings_dict["user_sync_interval_seconds"])
        else:
            # If no last run, next run is now + interval
            user_sync_next_run = datetime.utcnow() + timedelta(seconds=settings_dict["user_sync_interval_seconds"])

    library_sync_next_run = None
    if settings_dict.get("library_sync_enabled"):
        if settings_dict.get("library_sync_last_run"):
            last_run = datetime.fromisoformat(settings_dict["library_sync_last_run"])
            library_sync_next_run = last_run + timedelta(seconds=settings_dict["library_sync_interval_seconds"])
        else:
            # If no last run, next run is now + interval
            library_sync_next_run = datetime.utcnow() + timedelta(seconds=settings_dict["library_sync_interval_seconds"])

    return SyncSettingsResponse(
        user_sync_enabled=settings_dict["user_sync_enabled"],
        user_sync_interval_seconds=settings_dict["user_sync_interval_seconds"],
        user_sync_last_run=datetime.fromisoformat(settings_dict["user_sync_last_run"]) if settings_dict.get("user_sync_last_run") else None,
        user_sync_next_run=user_sync_next_run,

        library_sync_enabled=settings_dict["library_sync_enabled"],
        library_sync_interval_seconds=settings_dict["library_sync_interval_seconds"],
        library_passive_discovery=settings_dict["library_passive_discovery"],
        library_sync_last_run=datetime.fromisoformat(settings_dict["library_sync_last_run"]) if settings_dict.get("library_sync_last_run") else None,
        library_sync_next_run=library_sync_next_run,

        sessions_cache_interval_seconds=settings_dict["sessions_cache_interval_seconds"],
        analytics_cache_interval_seconds=settings_dict["analytics_cache_interval_seconds"],
        server_status_interval_seconds=settings_dict["server_status_interval_seconds"],
    )


@router.post("/sync")
async def update_sync_settings(
    settings: SyncSettingsRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update sync and cache refresh settings"""

    # Define all settings to save
    settings_to_save = {
        "user_sync_enabled": settings.user_sync_enabled,
        "user_sync_interval_seconds": settings.user_sync_interval_seconds,
        "library_sync_enabled": settings.library_sync_enabled,
        "library_sync_interval_seconds": settings.library_sync_interval_seconds,
        "library_passive_discovery": settings.library_passive_discovery,
        "sessions_cache_interval_seconds": settings.sessions_cache_interval_seconds,
        "analytics_cache_interval_seconds": settings.analytics_cache_interval_seconds,
        "server_status_interval_seconds": settings.server_status_interval_seconds,
    }

    # Update or create each setting
    for key, value in settings_to_save.items():
        setting = db.query(SystemSettings).filter_by(key=key).first()

        if not setting:
            setting = SystemSettings(
                key=key,
                value=value,
                category="sync",
                description=f"Sync setting: {key}",
                updated_by_id=current_user.id
            )
            db.add(setting)
        else:
            setting.value = value
            setting.updated_by_id = current_user.id

    db.commit()

    # Tasks will be triggered by periodic scheduler based on settings
    # No immediate trigger here to avoid import issues

    return {"success": True, "message": "Sync settings updated"}


@router.post("/sync/run-user-sync")
async def run_user_sync_now(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Manually trigger user sync task"""
    try:
        # Use Celery to send task to worker
        from celery import Celery
        import os

        # Create Celery app with same config as worker
        celery_app = Celery(
            'worker',
            broker=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
            backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0')
        )

        # Send task to worker queue
        result = celery_app.send_task('worker.tasks.sync_users_task')

        return {"success": True, "message": "User sync task queued successfully", "task_id": result.id}

    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to queue user sync task: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )


@router.post("/sync/run-library-sync")
async def run_library_sync_now(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Manually trigger library sync task"""
    try:
        # Use Celery to send task to worker
        from celery import Celery
        import os

        # Create Celery app with same config as worker
        celery_app = Celery(
            'worker',
            broker=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
            backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0')
        )

        # Send task to worker queue
        result = celery_app.send_task('worker.tasks.sync_libraries_task')

        return {"success": True, "message": "Library sync task queued successfully", "task_id": result.id}

    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to queue library sync task: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )