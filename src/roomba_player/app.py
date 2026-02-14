"""FastAPI entrypoint."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .aruco import ArucoService
from .camera import CameraService
from .config import settings
from .history import JsonlHistoryStore
from .odometry import OdometryEstimator
from .plan import PlanManager
from .roomba import RoombaOI
from .ws import control_stream, telemetry_stream

app = FastAPI(title="roomba-player", version="0.3.1")

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_DIR = WEB_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _asset_version() -> str:
    hasher = hashlib.sha256()
    files = sorted([p for p in WEB_DIR.rglob("*") if p.is_file()])
    for path in files:
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


def _render_template(filename: str, replacements: dict[str, str]) -> str:
    html = (WEB_DIR / filename).read_text(encoding="utf-8")
    html = html.replace("__ASSET_VERSION__", _asset_version())
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


@app.on_event("startup")
def startup() -> None:
    app.state.roomba = RoombaOI(
        port=settings.roomba_serial_port,
        baudrate=settings.roomba_baudrate,
        timeout=settings.roomba_timeout_sec,
    )
    app.state.odometry_history = JsonlHistoryStore(settings.odometry_history_path)
    app.state.odometry = OdometryEstimator(
        history_sink=app.state.odometry_history.append,
        source=settings.odometry_source,
        mm_per_tick=settings.odometry_mm_per_tick,
        linear_scale=settings.odometry_linear_scale,
        angular_scale=settings.odometry_angular_scale,
    )
    app.state.roomba.set_frame_callback(app.state.odometry.update_from_telemetry)
    app.state.plan = PlanManager()
    app.state.camera = CameraService(
        enabled=settings.camera_stream_enabled,
        width=settings.camera_width,
        height=settings.camera_height,
        framerate=settings.camera_framerate,
        profile=settings.camera_profile,
        shutter=settings.camera_shutter,
        denoise=settings.camera_denoise,
        sharpness=settings.camera_sharpness,
        awb=settings.camera_awb,
        h264_tcp_port=settings.camera_h264_tcp_port,
        http_bind_host=settings.camera_http_bind_host,
        http_port=settings.camera_http_port,
        http_path=settings.camera_http_path,
    )
    app.state.aruco = ArucoService(
        enabled=settings.aruco_enabled,
        interval_sec=settings.aruco_interval_sec,
        dictionary_name=settings.aruco_dictionary,
    )
    app.state.aruco.start()

    restored_pose = app.state.odometry_history.last_pose()
    if restored_pose:
        app.state.odometry.reset(
            x_mm=restored_pose.get("x_mm", 0),
            y_mm=restored_pose.get("y_mm", 0),
            theta_deg=restored_pose.get("theta_deg", 0),
        )

    if settings.plan_default_path:
        try:
            loaded = app.state.plan.load_from_file(settings.plan_default_path)
            if not restored_pose:
                start_pose = (loaded or {}).get("start_pose") or {}
                app.state.odometry.reset(
                    x_mm=start_pose.get("x_mm", 0),
                    y_mm=start_pose.get("y_mm", 0),
                    theta_deg=start_pose.get("theta_deg", 0),
                )
        except Exception:
            pass


@app.on_event("shutdown")
def shutdown() -> None:
    app.state.roomba.close()
    app.state.camera.stop()
    app.state.aruco.stop()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _render_template("home.html", {})


@app.get("/player", response_class=HTMLResponse)
def player() -> str:
    app.state.camera.start_if_enabled()
    return _render_template(
        "player.html",
        {
            "__CAMERA_ENABLED__": json.dumps(settings.camera_stream_enabled),
            "__ARUCO_ENABLED__": json.dumps(settings.aruco_enabled),
        },
    )


@app.post("/camera/start")
def camera_start() -> dict:
    return app.state.camera.start_if_enabled()


@app.get("/camera/stream")
def camera_stream():
    start = app.state.camera.start_if_enabled()
    if not start.get("enabled"):
        return JSONResponse({"ok": False, "error": "camera_disabled"}, status_code=404)
    if not start.get("started"):
        return JSONResponse({"ok": False, "error": start.get("reason", "camera_not_ready")}, status_code=503)
    try:
        _camera_proc, ffmpeg_proc = app.state.camera.open_stream_processes()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"camera_pipeline_error:{exc}"}, status_code=503)

    def stream_iter():
        aruco_buf = bytearray()
        next_aruco_at = 0.0
        try:
            while True:
                chunk = ffmpeg_proc.stdout.read(8192)
                if not chunk:
                    break
                if app.state.aruco.enabled:
                    aruco_buf.extend(chunk)
                    now = time.monotonic()
                    if now >= next_aruco_at:
                        data = bytes(aruco_buf)
                        start = data.rfind(b"\xff\xd8")
                        end = data.rfind(b"\xff\xd9")
                        if start >= 0 and end > start:
                            app.state.aruco.enqueue_jpeg_frame(data[start : end + 2])
                            next_aruco_at = now + app.state.aruco.interval_sec
                            if len(aruco_buf) > 128_000:
                                aruco_buf[:] = aruco_buf[-64_000:]
                        elif len(aruco_buf) > 1_000_000:
                            aruco_buf[:] = aruco_buf[-64_000:]
                yield chunk
        finally:
            app.state.camera.stop()

    return StreamingResponse(stream_iter(), media_type="multipart/x-mixed-replace; boundary=ffmpeg")


@app.get("/aruco/status")
def aruco_status() -> dict:
    return app.state.aruco.status()


@app.get("/aruco/debug")
def aruco_debug() -> dict:
    return app.state.aruco.debug()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


def _plan_start_pose() -> dict:
    plan = app.state.plan.get() or {}
    start_pose = plan.get("start_pose") or {}
    return {
        "x_mm": start_pose.get("x_mm", 0),
        "y_mm": start_pose.get("y_mm", 0),
        "theta_deg": start_pose.get("theta_deg", 0),
    }


@app.get("/api/plan")
def get_plan() -> dict:
    return {"plan": app.state.plan.get()}


@app.post("/api/plan/load-file")
def load_plan_file(payload: dict) -> dict:
    path = str(payload.get("path", "")).strip()
    if not path:
        return {"ok": False, "error": "missing_path"}
    try:
        plan = app.state.plan.load_from_file(path)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    start_pose = (plan or {}).get("start_pose") or {}
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
    )
    return {"ok": True}


@app.post("/api/plan/load-json")
def load_plan_json(payload: dict) -> dict:
    try:
        plan = app.state.plan.load_from_json(payload)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    start_pose = (plan or {}).get("start_pose") or {}
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
    )
    return {"ok": True}


@app.get("/api/odometry")
def get_odometry() -> dict:
    return app.state.odometry.get_pose()


@app.post("/api/odometry/reset")
def reset_odometry(payload: dict | None = None) -> dict:
    data = payload or {}
    app.state.odometry.reset(
        x_mm=data.get("x_mm", 0),
        y_mm=data.get("y_mm", 0),
        theta_deg=data.get("theta_deg", 0),
    )
    return {"ok": True, **app.state.odometry.get_pose()}


@app.post("/api/odometry/reset-history")
def reset_odometry_history() -> dict:
    app.state.odometry_history.clear()
    start_pose = _plan_start_pose()
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
    )
    return {"ok": True, "history_cleared": True, **app.state.odometry.get_pose()}


@app.get("/telemetry")
def telemetry() -> dict:
    payload = app.state.roomba.get_telemetry_snapshot()
    payload["odometry"] = app.state.odometry.get_pose()
    return payload


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await telemetry_stream(websocket, app.state.roomba, app.state.odometry, app.state.aruco)


@app.websocket("/ws/control")
async def control_ws(websocket: WebSocket) -> None:
    await control_stream(websocket, app.state.roomba, app.state.odometry)
