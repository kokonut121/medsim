from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.db.redis_client import redis_client


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/scans/{unit_id}/live")
async def websocket_scan_live(websocket: WebSocket, unit_id: str):
    await websocket.accept()
    channel = f"scan:{unit_id}"
    queue = await redis_client.subscribe(channel)
    try:
        while True:
            payload = await asyncio.wait_for(queue.get(), timeout=30)
            await websocket.send_json(payload)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        redis_client.unsubscribe(channel, queue)
        await websocket.close()

