"""Phase 4 WebSocket tests."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.utils.ws_manager import WebSocketManager


@pytest.mark.asyncio
async def test_ws_manager_connect():
    """WebSocket manager tracks connections."""
    manager = WebSocketManager()
    ws = AsyncMock()
    await manager.connect("debate-1", ws)
    ws.accept.assert_awaited_once()
    assert "debate-1" in manager._connections
    assert ws in manager._connections["debate-1"]


@pytest.mark.asyncio
async def test_ws_manager_disconnect():
    """WebSocket manager removes connections on disconnect."""
    manager = WebSocketManager()
    ws = AsyncMock()
    await manager.connect("debate-1", ws)
    manager.disconnect("debate-1", ws)
    assert ws not in manager._connections["debate-1"]


@pytest.mark.asyncio
async def test_ws_manager_broadcast_local():
    """Broadcast sends to all local connections."""
    manager = WebSocketManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect("debate-1", ws1)
    await manager.connect("debate-1", ws2)

    await manager.broadcast("debate-1", {"type": "test", "data": {}})

    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_ws_manager_broadcast_removes_dead_connections():
    """Broadcast removes connections that fail to send."""
    manager = WebSocketManager()
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = Exception("Connection closed")

    await manager.connect("debate-1", ws_alive)
    await manager.connect("debate-1", ws_dead)

    await manager.broadcast("debate-1", {"type": "test", "data": {}})

    # Dead connection should be removed
    assert ws_dead not in manager._connections["debate-1"]
    assert ws_alive in manager._connections["debate-1"]


@pytest.mark.asyncio
async def test_ws_manager_publish_event():
    """publish_event wraps event in type/data envelope."""
    manager = WebSocketManager()
    ws = AsyncMock()
    await manager.connect("debate-1", ws)

    await manager.publish_event("debate-1", "turn_submitted", {"turn_id": "abc"})

    ws.send_text.assert_awaited_once()
    import json
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "turn_submitted"
    assert sent["data"]["turn_id"] == "abc"


@pytest.mark.asyncio
async def test_ws_manager_broadcast_no_connections():
    """Broadcast to debate with no connections is a no-op."""
    manager = WebSocketManager()
    # Should not raise
    await manager.broadcast("nonexistent-debate", {"type": "test", "data": {}})


@pytest.mark.asyncio
async def test_ws_manager_multiple_debates():
    """Manager handles multiple debates independently."""
    manager = WebSocketManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect("debate-1", ws1)
    await manager.connect("debate-2", ws2)

    await manager.broadcast("debate-1", {"type": "test", "data": {}})

    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_ws_manager_subscribe_no_redis():
    """Subscribe returns immediately when Redis is not connected."""
    manager = WebSocketManager()
    ws = AsyncMock()
    # _redis is None by default, so subscribe should just return
    await manager.subscribe("debate-1", ws)
    # No error raised = pass
