from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import logging

from .core.config import settings
from .core.database import get_db, engine
from .models import Base
from .api.routes import auth, admin
from .api.routes import settings as settings_router
from .services.auth_service import AuthService
from .services.metrics_cache_service import metrics_cache
from .services.bandwidth_cache import start_bandwidth_tracking, stop_bandwidth_tracking

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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

    # Start bandwidth tracking
    await start_bandwidth_tracking(db)
    logging.info("Started bandwidth tracking service")

    yield

    # Stop background services on shutdown
    await metrics_cache.stop()
    logging.info("Stopped background metrics collection service")

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