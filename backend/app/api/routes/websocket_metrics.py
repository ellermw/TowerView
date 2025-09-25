"""
WebSocket endpoint for real-time metrics using cached data
"""
import asyncio
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...services.metrics_cache_service import metrics_cache
from ...core.security import verify_token

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections"""
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.metrics_tasks: Dict[str, asyncio.Task] = {}

    def connect(self, client_id: str, websocket: WebSocket):
        """Add a new connection for a client"""
        # Don't accept here - already accepted in the route
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections[client_id])}")

    def disconnect(self, client_id: str, websocket: WebSocket):
        """Remove a connection for a client"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
                # Cancel metrics task if exists
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

manager = ConnectionManager()

async def send_metrics_loop(client_id: str, server_ids: list):
    """Send metrics from cache to the client"""
    while client_id in manager.active_connections:
        try:
            # Get metrics from cache for all servers
            metrics_list = []
            for server_id in server_ids:
                cached_metrics = metrics_cache.get_metrics(server_id)
                if cached_metrics:
                    # Add server_id to the cached metrics
                    metric_data = cached_metrics.copy()
                    metric_data["server_id"] = server_id
                    metrics_list.append(metric_data)
                else:
                    # Send placeholder if no cached data yet
                    metrics_list.append({
                        "server_id": server_id,
                        "cpu_usage": 0,
                        "memory_usage": 0,
                        "memory_used_gb": 0,
                        "memory_total_gb": 0,
                        "container": None,
                        "gpu": {"available": False},
                        "timestamp": None
                    })

            # Send all metrics
            await manager.send_metrics(client_id, {
                "type": "metrics_update",
                "data": metrics_list
            })

            # Wait 2 seconds before next update
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error in metrics loop for client {client_id}: {e}")
            await asyncio.sleep(5)

@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics from cache"""
    client_id = None
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted, waiting for authentication")

        # Wait for initial message with token and server IDs
        data = await websocket.receive_json()
        token = data.get("token")
        server_ids = data.get("servers", [])

        logger.info(f"Received initial data: Token present: {bool(token)}, Servers: {server_ids}")

        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return

        # Verify token
        payload = verify_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return

        # Create unique client ID
        client_id = f"user_{user_id}"
        logger.info(f"Authenticated user: {payload.get('type', 'unknown')} (ID: {user_id})")

        # Connect the WebSocket
        manager.connect(client_id, websocket)

        # Start sending metrics from cache
        if server_ids and client_id not in manager.metrics_tasks:
            task = asyncio.create_task(send_metrics_loop(client_id, server_ids))
            manager.metrics_tasks[client_id] = task
            logger.info(f"Started metrics stream for client {client_id}, servers: {server_ids}")

        # Keep connection alive
        while True:
            # Wait for any message from client (heartbeat)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send ping to check connection
                try:
                    await websocket.send_text("ping")
                except:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for client {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if client_id:
            manager.disconnect(client_id, websocket)