from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import logging

from .core.config import settings
from .core.database import get_db, engine
from .models import Base
from .api.routes import auth, admin, media_user
from .api.routes import settings as settings_router
from .services.auth_service import AuthService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Towerview",
    description="Multi-Server Media Monitoring & Admin App",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "192.168.1.74", "*"]
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(media_user.router, prefix="/api/me", tags=["Media User"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])

# Import and include WebSocket router
from .api.routes import websocket
app.include_router(websocket.router, prefix="/api", tags=["WebSocket"])


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    # Create initial admin user if it doesn't exist
    db = next(get_db())
    auth_service = AuthService(db)
    await auth_service.create_initial_admin()
    db.close()


@app.get("/")
async def root():
    return {"message": "Towerview API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)