"""
Settings API routes - main aggregator
This module imports and combines all settings-related routes
"""
from fastapi import APIRouter

# Create main settings router
router = APIRouter()

# Import sub-routers
from .netdata import router as netdata_router
from .portainer import router as portainer_router
from .sync import router as sync_router
from .site import router as site_router

# Include all sub-routers
router.include_router(netdata_router, tags=["netdata"])
router.include_router(portainer_router, tags=["portainer"])
router.include_router(sync_router, tags=["sync"])
router.include_router(site_router, tags=["site"])