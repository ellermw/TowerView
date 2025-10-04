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
from .audit_logs import router as audit_logs_router
from .watch_history import router as watch_history_router

# Create main admin router
router = APIRouter()

# Include all sub-routers
router.include_router(servers_router, tags=["Servers"])
router.include_router(sessions_router, tags=["Sessions"])
router.include_router(users_router, tags=["Users"])
router.include_router(analytics_router, tags=["Analytics"])
router.include_router(libraries_router, tags=["Libraries"])
router.include_router(audit_logs_router, tags=["Audit Logs"])
router.include_router(watch_history_router, tags=["Watch History"])