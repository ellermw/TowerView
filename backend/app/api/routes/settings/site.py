"""
Site settings endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ....core.database import get_db
from ....core.security import get_current_admin_user
from ....models.user import User
from ....models.settings import SystemSettings

router = APIRouter()


class SiteSettingsRequest(BaseModel):
    site_name: str


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