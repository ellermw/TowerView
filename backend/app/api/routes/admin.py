"""
Admin API routes - main entry point
This module now imports and uses the modular admin routes
"""
from fastapi import APIRouter

# Import the modular admin router which includes all sub-modules
from .admin import router as admin_router

# For backward compatibility, export the router directly
router = admin_router