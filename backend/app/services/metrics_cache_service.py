"""
Background service for collecting and caching server metrics
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class MetricsCacheService:
    """Singleton service that collects metrics in the background"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.metrics_cache: Dict[int, Dict] = {}
            self.last_update: Optional[datetime] = None
            self.collection_task: Optional[asyncio.Task] = None
            self.is_running = False
            self._initialized = True
            logger.info("MetricsCacheService initialized")

    async def start(self):
        """Start the background metrics collection"""
        if self.is_running:
            logger.warning("Metrics collection already running")
            return

        self.is_running = True
        self.collection_task = asyncio.create_task(self._collect_metrics_loop())
        logger.info("Started background metrics collection")

    async def stop(self):
        """Stop the background metrics collection"""
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background metrics collection")

    async def _collect_metrics_loop(self):
        """Main loop that collects metrics from all servers"""
        while self.is_running:
            try:
                await self._collect_all_metrics()
                # Wait 2 seconds before next collection
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def _collect_all_metrics(self):
        """Collect metrics from all configured servers"""
        from ..core.database import SessionLocal
        from ..models.server import Server
        from ..models.settings import PortainerIntegration
        from ..services.portainer_service import PortainerService

        db = SessionLocal()
        try:
            # Get all active servers
            servers = db.query(Server).filter(Server.enabled == True).all()

            # Get Portainer integration settings
            portainer_integration = db.query(PortainerIntegration).filter(
                PortainerIntegration.enabled == True
            ).first()

            if not portainer_integration:
                logger.debug("No Portainer integration configured")
                return

            url = portainer_integration.url
            endpoint_id = portainer_integration.endpoint_id or 2

            if not url:
                logger.debug("No Portainer URL configured")
                return

            # Collect metrics for each server
            new_metrics = {}

            # Get container mappings
            container_mappings = portainer_integration.container_mappings or {}

            async with PortainerService(db) as portainer:
                # Get a fresh token (will auto-refresh if expired)
                api_token = await portainer._get_fresh_token(portainer_integration)
                if not api_token:
                    logger.debug("Failed to get Portainer API token")
                    return
                # Get all containers to resolve short IDs to full IDs
                all_containers = await portainer.get_containers(url, api_token, endpoint_id)
                container_id_map = {}
                if all_containers:
                    for container in all_containers:
                        # Map short ID (12 chars) to full ID
                        short_id = container.get('id', '')[:12]
                        full_id = container.get('id', '')
                        if short_id and full_id:
                            container_id_map[short_id] = full_id

                for server in servers:
                    try:
                        # Check if this server has a container mapping
                        mapping = container_mappings.get(str(server.id))
                        if not mapping:
                            logger.debug(f"No container mapped for server {server.id}")
                            continue

                        # Extract container ID from mapping (handle both dict and string formats)
                        if isinstance(mapping, dict):
                            container_id = mapping.get('container_id')
                        else:
                            container_id = mapping

                        if not container_id:
                            logger.debug(f"No container ID in mapping for server {server.id}")
                            continue

                        # Resolve to full ID if we have a short ID
                        if len(container_id) <= 12:
                            full_container_id = container_id_map.get(container_id, container_id)
                        else:
                            full_container_id = container_id

                        # Get container stats
                        stats = await portainer.get_container_stats(url, api_token, full_container_id, endpoint_id)

                        if stats:
                            # Stats are already processed by PortainerService
                            metrics = {
                                "cpu_usage": stats.get("cpu_percent", 0),
                                "memory_usage": stats.get("memory_percent", 0),
                                "memory_used_gb": stats.get("memory_usage_mb", 0) / 1024,
                                "memory_total_gb": stats.get("memory_limit_mb", 0) / 1024,
                                "container": container_id,
                                "gpu": {"available": False},
                                "timestamp": stats.get("timestamp")
                            }
                            new_metrics[server.id] = metrics
                            logger.debug(f"Collected metrics for server {server.id}: CPU={metrics['cpu_usage']:.1f}%, Memory={metrics['memory_usage']:.1f}%")

                    except Exception as e:
                        logger.error(f"Error collecting metrics for server {server.id}: {e}")

            # Update cache atomically
            self.metrics_cache = new_metrics
            self.last_update = datetime.utcnow()

            if new_metrics:
                logger.debug(f"Updated metrics cache for {len(new_metrics)} servers")

        except Exception as e:
            logger.error(f"Error in _collect_all_metrics: {e}")
        finally:
            db.close()

    def _process_container_stats(self, stats: Dict, container_id: str) -> Dict:
        """Process raw container stats into metrics format"""
        try:
            # CPU calculation
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]

            cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
            cpu_usage = 0.0
            if system_delta > 0:
                cpu_usage = (cpu_delta / system_delta) * cpu_count * 100

            # Memory calculation
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0

            # GPU detection
            gpu_info = {"available": False}

            # Check for NVIDIA GPU
            if "nvidia" in stats.get("name", "").lower() or \
               any("nvidia" in str(v).lower() for v in stats.get("Labels", {}).values()):
                gpu_info = {
                    "available": True,
                    "gpu_usage": 0,  # Would need nvidia-smi integration
                    "render_usage": 0,
                    "video_usage": 0
                }

            return {
                "cpu_usage": round(cpu_usage, 2),
                "memory_usage": round(memory_percent, 2),
                "memory_used_gb": round(memory_usage / (1024**3), 2),
                "memory_total_gb": round(memory_limit / (1024**3), 2) if memory_limit > 0 else 0,
                "container": container_id,
                "timestamp": datetime.utcnow().isoformat(),
                "gpu": gpu_info
            }
        except Exception as e:
            logger.error(f"Error processing container stats: {e}")
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "container": container_id,
                "timestamp": datetime.utcnow().isoformat(),
                "gpu": {"available": False}
            }

    def get_metrics(self, server_id: int) -> Optional[Dict]:
        """Get cached metrics for a specific server"""
        return self.metrics_cache.get(server_id)

    def get_all_metrics(self) -> Dict[int, Dict]:
        """Get all cached metrics"""
        return self.metrics_cache.copy()

    @property
    def cache_age(self) -> Optional[float]:
        """Get age of cache in seconds"""
        if self.last_update:
            return (datetime.utcnow() - self.last_update).total_seconds()
        return None

# Global instance
metrics_cache = MetricsCacheService()