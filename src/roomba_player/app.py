"""FastAPI entrypoint."""

from fastapi import FastAPI, WebSocket

from .config import settings
from .roomba import RoombaOI
from .telemetry import get_telemetry_snapshot
from .ws import control_stream, telemetry_stream

app = FastAPI(title="roomba-player", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    app.state.roomba = RoombaOI(
        port=settings.roomba_serial_port,
        baudrate=settings.roomba_baudrate,
        timeout=settings.roomba_timeout_sec,
    )


@app.on_event("shutdown")
def shutdown() -> None:
    app.state.roomba.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/telemetry")
def telemetry() -> dict:
    payload = get_telemetry_snapshot()
    payload["roomba_connected"] = app.state.roomba.connected
    return payload


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await telemetry_stream(websocket)


@app.websocket("/ws/control")
async def control_ws(websocket: WebSocket) -> None:
    await control_stream(websocket, app.state.roomba)
