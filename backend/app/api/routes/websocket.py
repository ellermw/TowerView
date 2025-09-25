import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError

from ...core.websocket import get_connection_manager
from ...core.security import verify_token

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


async def get_current_user_ws(websocket: WebSocket, token: str):
    """Get current user from WebSocket token"""
    try:
        payload = verify_token(token)
        if payload is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        user_id = payload.get("sub")
        user_type = payload.get("type")

        if not user_id or not user_type:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        return {"id": int(user_id), "type": user_type}

    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """WebSocket endpoint for real-time updates"""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Authenticate user
    user = await get_current_user_ws(websocket, token)
    if not user:
        return

    manager = get_connection_manager()

    try:
        # Connect the WebSocket
        await manager.connect(websocket, str(user["id"]), user["type"])

        # Send initial connection message
        await manager.send_personal_message(
            json.dumps({
                "type": "connection",
                "message": "Connected to Towerview real-time updates"
            }),
            websocket
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for incoming messages (client can send heartbeat, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping/pong for connection health
                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Invalid JSON, ignore
                continue
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Disconnect the WebSocket
        await manager.disconnect(websocket, str(user["id"]), user["type"])