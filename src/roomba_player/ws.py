"""WebSocket handlers."""

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from .config import settings
from .roomba import RoombaOI


def _normalize_radius(radius: int) -> int:
    radius = int(radius)
    if radius in (32768, -1, 1):
        return radius
    return max(-2000, min(2000, radius))


async def telemetry_stream(websocket: WebSocket, roomba: RoombaOI) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(roomba.get_telemetry_snapshot())
            await asyncio.sleep(settings.telemetry_interval_sec)
    except WebSocketDisconnect:
        return


def handle_control_message(message: dict, roomba: RoombaOI) -> dict:
    action = str(message.get("action", "")).lower()
    if not action:
        raise ValueError("Missing `action` in message.")

    if action == "ping":
        return {"ok": True, "action": "pong", "connected": roomba.connected}

    if action == "init":
        roomba.connect()
        roomba.start()
        roomba.safe()
        roomba.start_sensor_stream()
        return {"ok": True, "action": action, "connected": roomba.connected}

    if action == "mode":
        mode = str(message.get("value", "safe")).lower()
        if mode == "safe":
            roomba.safe()
        elif mode == "full":
            roomba.full()
        else:
            raise ValueError("`mode` value must be `safe` or `full`.")
        return {"ok": True, "action": action, "mode": mode, "connected": roomba.connected}

    if action == "drive":
        velocity = int(message.get("velocity", 0))
        radius = int(message.get("radius", 0))
        roomba.drive(velocity=velocity, radius=radius)
        return {
            "ok": True,
            "action": action,
            "velocity": max(-500, min(500, velocity)),
            "radius": _normalize_radius(radius),
            "connected": roomba.connected,
        }

    if action == "stop":
        roomba.stop()
        return {"ok": True, "action": action, "connected": roomba.connected}

    if action == "clean":
        roomba.clean()
        return {"ok": True, "action": action, "connected": roomba.connected}

    if action == "dock":
        roomba.dock()
        return {"ok": True, "action": action, "connected": roomba.connected}

    raise ValueError(f"Unsupported action: {action}")


async def control_stream(websocket: WebSocket, roomba: RoombaOI) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "protocol": "roomba-oi-v1",
            "actions": ["ping", "init", "mode", "drive", "stop", "clean", "dock"],
        }
    )
    try:
        while True:
            message = await websocket.receive_json()
            try:
                response = handle_control_message(message=message, roomba=roomba)
                await websocket.send_json({"type": "ack", **response})
            except Exception as exc:
                await websocket.send_json({"type": "error", "ok": False, "error": str(exc)})
    except WebSocketDisconnect:
        return
