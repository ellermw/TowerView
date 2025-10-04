"""
Container Sync Service - Automatically syncs container mappings periodically
"""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.settings import PortainerIntegration
from .portainer_service import PortainerService

logger = logging.getLogger(__name__)

class ContainerSyncService:
    """Service to automatically sync container mappings periodically"""

    SYNC_INTERVAL = 300  # Sync every 5 minutes
    _running = False
    _task = None

    @classmethod
    async def start(cls):
        """Start the background sync service"""
        if cls._running:
            logger.warning("Container sync service already running")
            return

        cls._running = True
        cls._task = asyncio.create_task(cls._sync_loop())
        logger.info("Container sync service started")

    @classmethod
    async def stop(cls):
        """Stop the background sync service"""
        if not cls._running:
            return

        cls._running = False
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
        logger.info("Container sync service stopped")

    @classmethod
    async def _sync_loop(cls):
        """Main sync loop that runs periodically"""
        while cls._running:
            try:
                await cls._perform_sync()
                await asyncio.sleep(cls.SYNC_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in container sync loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    @classmethod
    async def _perform_sync(cls):
        """Perform a single sync operation"""
        db = SessionLocal()
        try:
            # Get Portainer integration
            integration = db.query(PortainerIntegration).filter(
                PortainerIntegration.enabled == True
            ).first()

            if not integration:
                logger.debug("No Portainer integration configured, skipping sync")
                return

            # Check if sync is needed (at least 5 minutes since last update)
            if integration.updated_at:
                time_since_update = datetime.utcnow() - integration.updated_at
                if time_since_update < timedelta(minutes=5):
                    logger.debug(f"Skipping sync, last updated {time_since_update.seconds} seconds ago")
                    return

            # Perform the sync
            async with PortainerService(db) as service:
                success = await service.sync_container_mappings(integration)

            if success:
                logger.info("Container mappings synced successfully")
            else:
                logger.warning("Container mapping sync failed")

        except Exception as e:
            logger.error(f"Error performing container sync: {e}")
        finally:
            db.close()

    @classmethod
    async def sync_now(cls):
        """Trigger an immediate sync"""
        await cls._perform_sync()