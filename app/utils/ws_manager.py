import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import WebSocket
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._redis: Optional[aioredis.Redis] = None

    async def connect_redis(self):
        if not self._redis:
            self._redis = aioredis.from_url(settings.REDIS_URL)

    async def connect(self, debate_id: str, websocket: WebSocket):
        await websocket.accept()
        if debate_id not in self._connections:
            self._connections[debate_id] = []
        self._connections[debate_id].append(websocket)

    def disconnect(self, debate_id: str, websocket: WebSocket):
        if debate_id in self._connections:
            self._connections[debate_id] = [
                ws for ws in self._connections[debate_id] if ws != websocket
            ]

    async def broadcast(self, debate_id: str, event: dict):
        """Send event to all connected clients for a debate."""
        message = json.dumps(event)

        # Local connections
        if debate_id in self._connections:
            dead = []
            for ws in self._connections[debate_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(debate_id, ws)

        # Redis pub/sub for multi-instance
        if self._redis:
            try:
                await self._redis.publish(f"debate:{debate_id}", message)
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")

    async def publish_event(self, debate_id: str, event_type: str, data: dict):
        """Convenience method to publish a typed event."""
        await self.broadcast(debate_id, {"type": event_type, "data": data})

    async def subscribe(self, debate_id: str, websocket: WebSocket):
        """Subscribe to Redis channel and forward messages."""
        if not self._redis:
            return

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(f"debate:{debate_id}")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"].decode() if isinstance(message["data"], bytes) else message["data"])
                    except Exception:
                        break
        finally:
            await pubsub.unsubscribe(f"debate:{debate_id}")


ws_manager = WebSocketManager()


async def publish_event_via_redis(debate_id: str, event_type: str, data: dict):
    """Publish a WebSocket event directly to Redis. Usable from Celery tasks."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        message = json.dumps({"type": event_type, "data": data})
        await r.publish(f"debate:{debate_id}", message)
    finally:
        await r.aclose()
