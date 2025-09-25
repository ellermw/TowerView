import json
import asyncio
import redis.asyncio as redis
from typing import Dict, Set
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, redis_url: str):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_url = redis_url
        self.redis_client = None
        self.pubsub = None

    async def connect(self, websocket: WebSocket, user_id: str, user_type: str):
        """Connect a new WebSocket client"""
        await websocket.accept()

        # Add to appropriate room based on user type
        room = f"{user_type}:{user_id}" if user_type == "media_user" else "admin"

        if room not in self.active_connections:
            self.active_connections[room] = set()

        self.active_connections[room].add(websocket)
        logger.info(f"WebSocket connected: {room}")

        # Initialize Redis connection if needed
        if not self.redis_client:
            await self.init_redis()

    async def disconnect(self, websocket: WebSocket, user_id: str, user_type: str):
        """Disconnect a WebSocket client"""
        room = f"{user_type}:{user_id}" if user_type == "media_user" else "admin"

        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]

        logger.info(f"WebSocket disconnected: {room}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_room(self, room: str, message: dict):
        """Broadcast message to all connections in a room"""
        if room not in self.active_connections:
            return

        message_str = json.dumps(message)
        disconnected = set()

        for connection in self.active_connections[room]:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.active_connections[room].discard(connection)

    async def broadcast_to_admins(self, message: dict):
        """Broadcast message to all admin connections"""
        await self.broadcast_to_room("admin", message)

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific media user"""
        room = f"media_user:{user_id}"
        await self.broadcast_to_room(room, message)

    async def init_redis(self):
        """Initialize Redis connection for pub/sub"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("towerview:sessions", "towerview:servers")

            # Start background task to listen for Redis messages
            asyncio.create_task(self.redis_listener())
            logger.info("Redis pub/sub initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")

    async def redis_listener(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket clients"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode()
                    data = json.loads(message["data"].decode())

                    await self.handle_redis_message(channel, data)
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")

    async def handle_redis_message(self, channel: str, data: dict):
        """Handle incoming Redis pub/sub messages"""
        if channel == "towerview:sessions":
            # Broadcast session updates to admins
            await self.broadcast_to_admins({
                "type": "session_update",
                "data": data
            })

            # If session belongs to a specific user, send to them too
            if "user_id" in data:
                await self.send_to_user(str(data["user_id"]), {
                    "type": "session_update",
                    "data": data
                })

        elif channel == "towerview:servers":
            # Broadcast server updates to admins only
            await self.broadcast_to_admins({
                "type": "server_update",
                "data": data
            })

    async def publish_session_update(self, session_data: dict):
        """Publish session update to Redis"""
        if self.redis_client:
            try:
                await self.redis_client.publish(
                    "towerview:sessions",
                    json.dumps(session_data)
                )
            except Exception as e:
                logger.error(f"Error publishing session update: {e}")

    async def publish_server_update(self, server_data: dict):
        """Publish server update to Redis"""
        if self.redis_client:
            try:
                await self.redis_client.publish(
                    "towerview:servers",
                    json.dumps(server_data)
                )
            except Exception as e:
                logger.error(f"Error publishing server update: {e}")

    async def close(self):
        """Close Redis connections"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()


# Global connection manager instance
manager = None


def get_connection_manager() -> ConnectionManager:
    global manager
    if manager is None:
        from .config import settings
        manager = ConnectionManager(settings.redis_url)
    return manager