import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# NOTE: WebSocket endpoint is intentionally unauthenticated.
# Debate streams are public — any client can subscribe to live updates.
# No mutations are accepted over WS; it is read-only (server→client events).
@router.websocket("/ws/debates/{debate_id}")
async def debate_websocket(websocket: WebSocket, debate_id: str):
    await ws_manager.connect(debate_id, websocket)
    try:
        # Start Redis subscriber in background
        subscribe_task = asyncio.create_task(
            ws_manager.subscribe(debate_id, websocket)
        )

        # Keep connection alive — wait for disconnect
        while True:
            try:
                data = await websocket.receive_text()
                # Clients can send ping/pong but no mutations via WS
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for debate {debate_id}: {e}")
    finally:
        ws_manager.disconnect(debate_id, websocket)
        subscribe_task.cancel()
