"""FastAPI entrypoint."""

from fastapi import FastAPI, WebSocket

from .config import settings
from .telemetry import get_telemetry_snapshot
from .ws import telemetry_stream

app = FastAPI(title="roomba-player", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/telemetry")
def telemetry() -> dict:
    return get_telemetry_snapshot()


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await telemetry_stream(websocket)
