"""FastAPI entrypoint."""

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from .config import settings
from .roomba import RoombaOI
from .telemetry import get_telemetry_snapshot
from .ws import control_stream, telemetry_stream

app = FastAPI(title="roomba-player", version="0.1.0")

HOME_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>roomba-player</title>
    <style>
      body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; line-height: 1.4; max-width: 800px; }
      h1, h2 { margin-bottom: 0.4rem; }
      code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 4px; }
      ul { margin-top: 0.3rem; }
    </style>
  </head>
  <body>
    <h1>roomba-player</h1>
    <p>Short project summary: control, monitor and (later) auto-pilot a Roomba from a Raspberry Pi over HTTP/WebSocket.</p>

    <h2>Current API</h2>
    <ul>
      <li><code>GET /health</code></li>
      <li><code>GET /telemetry</code></li>
      <li><code>WS /ws/telemetry</code></li>
      <li><code>WS /ws/control</code></li>
    </ul>

    <h2>Current WebSocket commands (<code>/ws/control</code>)</h2>
    <ul>
      <li><code>ping</code></li>
      <li><code>init</code></li>
      <li><code>mode</code> with <code>safe|full</code></li>
      <li><code>drive</code> with <code>velocity</code> and <code>radius</code></li>
      <li><code>stop</code></li>
      <li><code>clean</code></li>
      <li><code>dock</code></li>
    </ul>
  </body>
</html>
"""


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


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HOME_PAGE


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
