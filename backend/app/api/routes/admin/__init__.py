"""
Admin API routes package
Split into logical modules for better organization
"""
from fastapi import APIRouter

# Import sub-routers
from .servers import router as servers_router
from .sessions import router as sessions_router
from .users import router as users_router
from .analytics import router as analytics_router
from .libraries import router as libraries_router

# Create main admin router
router = APIRouter()

# Include all sub-routers
router.include_router(servers_router, tags=["Servers"])
router.include_router(sessions_router, tags=["Sessions"])
router.include_router(users_router, tags=["Users"])
router.include_router(analytics_router, tags=["Analytics"])
router.include_router(libraries_router, tags=["Libraries"])