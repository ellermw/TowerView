from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import logging

from .core.config import settings
from .core.database import get_db, engine
from .models import Base
from .api.routes import auth, admin, users
from .api.routes import settings as settings_router
from .services.auth_service import AuthService
from .services.metrics_cache_service import metrics_cache
from .services.bandwidth_cache import start_bandwidth_tracking, stop_bandwidth_tracking
from .services.sessions_cache_service import sessions_cache_service
from .services.users_cache_service import users_cache_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable DEBUG logging for Plex provider to debug HW transcoding
logging.getLogger("app.providers.plex").setLevel(logging.DEBUG)

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Initialize on startup
    db = next(get_db())
    auth_service = AuthService(db)
    await auth_service.create_initial_admin()
    db.close()

    # Start background metrics collection
    await metrics_cache.start()
    logging.info("Started background metrics collection service")

    # Start sessions cache service
    await sessions_cache_service.start()
    logging.info("Started sessions cache service")

    # Start users cache service
    await users_cache_service.start()
    logging.info("Started users cache service")

    # Start bandwidth tracking
    await start_bandwidth_tracking(db)
    logging.info("Started bandwidth tracking service")

    yield

    # Stop background services on shutdown
    await metrics_cache.stop()
    logging.info("Stopped background metrics collection service")

    await sessions_cache_service.stop()
    logging.info("Stopped sessions cache service")

    await users_cache_service.stop()
    logging.info("Stopped users cache service")

    stop_bandwidth_tracking()
    logging.info("Stopped bandwidth tracking service")

app = FastAPI(
    title="Towerview",
    description="Multi-Server Media Monitoring & Admin App",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

# Import and include WebSocket router
from .api.routes import websocket_metrics
app.include_router(websocket_metrics.router, prefix="/api", tags=["WebSocket"])


@app.get("/")
async def root():
    return {"message": "Towerview API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)