from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from typing import Dict, Set
from ...core.database import get_db
from ...models.settings import PortainerIntegration
from ...models.user import User
from ...services.portainer_service import PortainerService
from ...core.security import get_current_user_from_token

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    """Manages WebSocket connections for real-time metrics"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.metrics_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections[client_id])}")

    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
                # Cancel the metrics task if no more connections
                if client_id in self.metrics_tasks:
                    self.metrics_tasks[client_id].cancel()
                    del self.metrics_tasks[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def send_metrics(self, client_id: str, data: dict):
        """Send metrics to all connections for a specific client"""
        if client_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending to client {client_id}: {e}")
                    disconnected.add(connection)

            # Remove disconnected clients
            for conn in disconnected:
                self.active_connections[client_id].discard(conn)

    async def broadcast_notification(self, data: dict):
        """Broadcast a notification to all connected admin clients"""
        logger.info(f"Broadcasting notification to all clients: {data.get('type')}")
        disconnected = []

        for client_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error broadcasting to client {client_id}: {e}")
                    disconnected.append((client_id, connection))

        # Remove disconnected clients
        for client_id, conn in disconnected:
            if client_id in self.active_connections:
                self.active_connections[client_id].discard(conn)

manager = ConnectionManager()


async def fetch_server_metrics(
    server_id: int,
    user_id: int
) -> dict:
    """Fetch metrics for a specific server from cache"""
    # Import metrics cache service
    from ...services.metrics_cache_service import metrics_cache

    # Try to get metrics from cache first
    cached_metrics = metrics_cache.get_metrics(server_id)
    if cached_metrics:
        # Add server_id to the cached metrics
        cached_metrics["server_id"] = server_id
        return cached_metrics

    # If no cached metrics, return empty metrics
    # The cache will be populated by the background service
    from ...core.database import SessionLocal
    db = SessionLocal()
    try:
        # Get container name for display
        from ...models.settings import Settings
        settings = db.query(Settings).filter(
            Settings.category == "portainer",
            Settings.key == f"server_{server_id}_container"
        ).first()

        container_name = settings.value if settings else None

        if not integration or not integration.api_token:
            return {
                "server_id": server_id,
                "error": "Portainer not configured",
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "container": None,
                "gpu": {"available": False}
            }

        # Get container mapping
        mappings = integration.container_mappings or {}
        server_mapping = mappings.get(str(server_id))

        if not server_mapping:
            return {
                "server_id": server_id,
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "gpu": {"available": False}
            }

        container_id = server_mapping.get("container_id")
        container_name = server_mapping.get("container_name")

        try:
            async with PortainerService(db) as service:
                # Fetch CPU/Memory and GPU stats in parallel
                stats_task = service.get_container_stats(
                    integration.url, integration.api_token, container_id, integration.endpoint_id
                )
                gpu_task = service.get_gpu_stats(
                    integration.url, integration.api_token, container_id, integration.endpoint_id
                )

                stats, gpu_stats = await asyncio.gather(stats_task, gpu_task, return_exceptions=True)

                # Handle exceptions from gather
                if isinstance(stats, Exception):
                    logger.debug(f"Error fetching stats for server {server_id}: {stats}")
                    stats = None
                if isinstance(gpu_stats, Exception):
                    logger.debug(f"Error fetching GPU stats for server {server_id}: {gpu_stats}")
                    gpu_stats = {"available": False}

                if not stats:
                    return {
                        "server_id": server_id,
                        "cpu_usage": 0,
                        "memory_usage": 0,
                        "memory_used_gb": 0,
                        "memory_total_gb": 0,
                        "container": container_name,
                        "gpu": {"available": False}
                    }

                return {
                    "server_id": server_id,
                    "cpu_usage": stats.get("cpu_percent", 0),
                    "memory_usage": stats.get("memory_percent", 0),
                    "memory_used_gb": stats.get("memory_usage_mb", 0) / 1024,
                    "memory_total_gb": stats.get("memory_limit_mb", 0) / 1024,
                    "container": container_name,
                    "timestamp": stats.get("timestamp"),
                    "gpu": gpu_stats
                }
        except Exception as e:
            logger.error(f"Error in fetch_server_metrics for server {server_id}: {e}")
            return {
                "server_id": server_id,
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "container": container_name if 'container_name' in locals() else None,
                "gpu": {"available": False}
            }
    finally:
        db.close()


async def metrics_streamer(
    client_id: str,
    server_ids: list,
    user_id: int
):
    """Continuously stream metrics for specified servers"""
    logger.info(f"Starting metrics stream for client {client_id}, servers: {server_ids}")

    while client_id in manager.active_connections:
        try:
            # Fetch metrics for all requested servers in parallel
            tasks = [
                fetch_server_metrics(server_id, user_id)
                for server_id in server_ids
            ]

            metrics_list = await asyncio.gather(*tasks)

            # Debug log
            logger.info(f"Sending metrics to {client_id}: {len(metrics_list)} server metrics")
            for m in metrics_list[:2]:  # Log first 2
                if isinstance(m, dict):
                    logger.info(f"  Server {m.get('server_id', 'unknown')}: CPU={m.get('cpu_usage', 0):.1f}%, Mem={m.get('memory_usage', 0):.1f}%, Container={m.get('container', 'none')}")

            # Send to client
            await manager.send_metrics(client_id, {
                "type": "metrics_update",
                "data": metrics_list
            })

            # Sleep briefly to control update rate (500ms for smooth real-time)
            await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info(f"Metrics stream cancelled for client {client_id}")
            break
        except Exception as e:
            logger.error(f"Error in metrics stream for client {client_id}: {e}")
            await asyncio.sleep(2)  # Back off on error


@router.websocket("/ws/metrics")
async def websocket_metrics(
    websocket: WebSocket
):
    """WebSocket endpoint for real-time server metrics"""
    await websocket.accept()

    # Get token and servers from the first message
    try:
        initial_data = await websocket.receive_text()
        logger.info(f"Received initial data: {initial_data[:100]}...")  # Log first 100 chars
        initial_msg = json.loads(initial_data)

        token = initial_msg.get("token")
        servers = initial_msg.get("servers", [])

        logger.info(f"Token present: {bool(token)}, Servers: {servers}")

        # Create a new session just for authentication
        from ...core.database import SessionLocal
        db = SessionLocal()
        try:
            # Authenticate user from token
            user = get_current_user_from_token(token, db)
            if not user:
                logger.error("User not found from token")
                await websocket.close(code=4003, reason="Unauthorized")
                return

            # Compare enum values properly
            from ...models.user import UserType
            if user.type != UserType.admin:
                logger.error(f"User is not admin: {user.type}")
                await websocket.close(code=4003, reason="Unauthorized")
                return

            # Store user info we need
            user_id = user.id
            username = user.username
            logger.info(f"Authenticated user: {username} (ID: {user_id})")
        finally:
            # Always close the db session
            db.close()
    except Exception as e:
        logger.error(f"Initial auth error: {e}", exc_info=True)
        await websocket.close(code=4003, reason="Invalid initial message")
        return

    client_id = f"user_{user_id}"
    server_ids = servers if isinstance(servers, list) else []

    # Register client (without accepting again)
    if client_id not in manager.active_connections:
        manager.active_connections[client_id] = set()
    manager.active_connections[client_id].add(websocket)
    logger.info(f"Client {client_id} connected. Total connections: {len(manager.active_connections[client_id])}")

    try:
        # Start metrics streaming task if not already running
        if client_id not in manager.metrics_tasks and server_ids:
            task = asyncio.create_task(
                metrics_streamer(client_id, server_ids, user_id)
            )
            manager.metrics_tasks[client_id] = task

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "subscribe":
                # Update server list
                new_servers = message.get("servers", [])
                if new_servers:
                    # Cancel old task
                    if client_id in manager.metrics_tasks:
                        manager.metrics_tasks[client_id].cancel()

                    # Start new task with updated servers
                    task = asyncio.create_task(
                        metrics_streamer(client_id, new_servers, user_id)
                    )
                    manager.metrics_tasks[client_id] = task

            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, client_id)