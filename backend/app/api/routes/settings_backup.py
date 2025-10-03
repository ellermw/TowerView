"""
Settings API routes - main entry point
This module now imports and uses the modular settings routes
"""
from fastapi import APIRouter

# Import the modular settings router which includes all sub-modules
from .settings import router as settings_router

# For backward compatibility, export the router directly
router = settings_router