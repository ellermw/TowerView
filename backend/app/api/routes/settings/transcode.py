"""
API routes for transcode settings
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, Field

from ....core.database import get_db
from ....core.security import get_current_admin_user
from ....models.user import User
from ....models.audit_log import AuditLog
from ....services.transcode_termination_service import TranscodeTerminationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcode", tags=["settings"])


class TranscodeSettings(BaseModel):
    """Model for transcode settings"""
    auto_terminate_4k_enabled: bool = Field(description="Enable automatic termination of 4K transcodes")
    auto_terminate_message: str = Field(description="Message to display when terminating (Plex only)")
    selected_server_ids: List[int] = Field(default=[], description="Server IDs to apply auto-termination to")


class TranscodeSettingsResponse(TranscodeSettings):
    """Response model for transcode settings"""
    pass


@router.get("/settings", response_model=TranscodeSettingsResponse)
async def get_transcode_settings(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get current transcode settings"""

    settings = TranscodeTerminationService.get_settings(db)

    return TranscodeSettingsResponse(
        auto_terminate_4k_enabled=settings["enabled"],
        auto_terminate_message=settings["message"],
        selected_server_ids=settings["server_ids"]
    )


@router.put("/settings")
async def update_transcode_settings(
    settings: TranscodeSettings,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update transcode settings"""

    try:
        # Update settings
        TranscodeTerminationService.update_settings(
            db=db,
            enabled=settings.auto_terminate_4k_enabled,
            message=settings.auto_terminate_message,
            server_ids=settings.selected_server_ids,
            updated_by_id=current_user.id
        )

        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="update_transcode_settings",
            target_type="settings",
            target_id=None,
            details={
                "enabled": settings.auto_terminate_4k_enabled,
                "message": settings.auto_terminate_message,
                "selected_servers": settings.selected_server_ids,
                "server_count": len(settings.selected_server_ids)
            }
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"User {current_user.username} updated transcode settings")

        return {"message": "Transcode settings updated successfully"}

    except Exception as e:
        logger.error(f"Error updating transcode settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )