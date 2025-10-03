"""
Sync settings endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import os

from ....core.database import get_db
from ....core.security import get_current_admin_user
from ....models.user import User
from ....models.settings import SystemSettings

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.get("/sync", response_model=SyncSettingsResponse)
async def get_sync_settings(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get sync and cache refresh settings"""
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
        logger.error(f"Failed to queue library sync task: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )