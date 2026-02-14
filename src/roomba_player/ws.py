"""WebSocket handlers."""

import asyncio

from fastapi import WebSocket

from .config import settings
from .telemetry import get_telemetry_snapshot


async def telemetry_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_telemetry_snapshot())
            await asyncio.sleep(settings.telemetry_interval_sec)
    finally:
        await websocket.close()
