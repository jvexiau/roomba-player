"""FastAPI entrypoint."""

from __future__ import annotations

import hashlib
import json
import math
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

app = FastAPI(title="roomba-player", version="0.6.0")

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


def _apply_plan_collision_constraints(plan: dict | None) -> None:
    app.state.odometry.set_collision_plan(
        plan=plan,
        robot_radius_mm=settings.odometry_robot_radius_mm,
    )


def _normalize_angle_deg(value: float) -> float:
    a = float(value)
    while a > 180.0:
        a -= 360.0
    while a < -180.0:
        a += 360.0
    return a


def _aruco_observed_size_px(marker: dict) -> float | None:
    corners = marker.get("corners")
    if not (isinstance(corners, list) and len(corners) == 4):
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in corners]
    except Exception:
        return None
    edges = []
    for i in range(4):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % 4]
        edges.append(math.hypot(x2 - x1, y2 - y1))
    if not edges:
        return None
    return float(sum(edges) / len(edges))


def _aruco_axis_and_base_distance(marker_cfg: dict) -> tuple[float, float, float] | None:
    try:
        mx = float(marker_cfg.get("x_mm", 0.0))
        my = float(marker_cfg.get("y_mm", 0.0))
    except Exception:
        return None
    snap_pose = marker_cfg.get("snap_pose")
    if isinstance(snap_pose, dict) and ("x_mm" in snap_pose) and ("y_mm" in snap_pose):
        try:
            sx = float(snap_pose.get("x_mm"))
            sy = float(snap_pose.get("y_mm"))
        except Exception:
            sx = mx
            sy = my
        vx = sx - mx
        vy = sy - my
        norm = math.hypot(vx, vy)
        if norm > 1e-6:
            return (vx / norm, vy / norm, norm)
    theta_deg = float(marker_cfg.get("theta_deg", 0.0) or 0.0)
    axis_x = math.cos(math.radians(theta_deg))
    axis_y = math.sin(math.radians(theta_deg))
    base = float(marker_cfg.get("front_offset_mm", 0.0) or 0.0)
    return (axis_x, axis_y, base)


def _compute_aruco_target_pose(marker_cfg: dict, marker: dict, frame_width: int) -> tuple[float, float, float] | None:
    axis_data = _aruco_axis_and_base_distance(marker_cfg)
    if axis_data is None:
        return None
    axis_x, axis_y, _base_dist = axis_data
    marker_x = float(marker_cfg.get("x_mm", 0.0) or 0.0)
    marker_y = float(marker_cfg.get("y_mm", 0.0) or 0.0)
    size_mm = max(1.0, float(marker_cfg.get("size_mm", 150.0) or 150.0))
    marker_px = _aruco_observed_size_px(marker)
    if marker_px is None or marker_px <= 1.0:
        return None
    est_dist = (float(settings.aruco_focal_px) * size_mm) / marker_px
    est_dist = max(50.0, min(6000.0, est_dist))
    target_x = marker_x + axis_x * est_dist
    target_y = marker_y + axis_y * est_dist
    base_heading = math.degrees(math.atan2(-axis_y, -axis_x))
    center = marker.get("center") if isinstance(marker.get("center"), list) else None
    cx = float(center[0]) if center and len(center) == 2 else (frame_width * 0.5)
    fw = max(1.0, float(frame_width or 1.0))
    heading_offset = ((cx / fw) - 0.5) * float(settings.aruco_heading_gain_deg)
    target_theta = _normalize_angle_deg(base_heading + heading_offset)
    return (target_x, target_y, target_theta)


def _apply_aruco_odometry_snap(result: dict) -> bool:
    if not settings.aruco_snap_enabled:
        return False
    if not isinstance(result, dict) or not result.get("ok"):
        return False
    markers = result.get("markers")
    if not isinstance(markers, list) or not markers:
        return False
    plan = app.state.plan.get() or {}
    plan_markers = plan.get("aruco_markers") if isinstance(plan, dict) else None
    if not isinstance(plan_markers, list) or not plan_markers:
        return False
    marker_index: dict[int, dict] = {}
    for m in plan_markers:
        if not isinstance(m, dict) or "id" not in m:
            continue
        try:
            marker_index[int(m.get("id"))] = m
        except Exception:
            continue
    if not marker_index:
        return False
    frame_width = int(result.get("frame_width", 0) or 0)
    ranked = sorted(
        [m for m in markers if isinstance(m, dict) and "id" in m],
        key=lambda m: float(m.get("area_px", 0.0) or 0.0),
        reverse=True,
    )
    for marker in ranked:
        try:
            marker_id = int(marker.get("id"))
        except Exception:
            continue
        marker_cfg = marker_index.get(marker_id)
        if marker_cfg is None:
            continue
        pose = _compute_aruco_target_pose(marker_cfg, marker, frame_width)
        if pose is None:
            continue
        app.state.odometry.apply_external_pose(
            x_mm=pose[0],
            y_mm=pose[1],
            theta_deg=pose[2],
            blend_pos=settings.aruco_pose_blend,
            blend_theta=settings.aruco_theta_blend,
            source="aruco_snap",
        )
        return True
    return False


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
    app.state.aruco_last_snap_key = None

    def _on_aruco_result(result: dict) -> None:
        if not isinstance(result, dict):
            return
        if not result.get("ok"):
            return
        ts = str(result.get("timestamp") or "")
        id_list: list[int] = []
        for m in (result.get("markers") or []):
            if not isinstance(m, dict) or "id" not in m:
                continue
            try:
                id_list.append(int(m.get("id")))
            except Exception:
                continue
        ids = tuple(sorted(id_list))
        snap_key = (ts, ids)
        if snap_key == app.state.aruco_last_snap_key:
            return
        if _apply_aruco_odometry_snap(result):
            app.state.aruco_last_snap_key = snap_key

    app.state.aruco.set_result_callback(_on_aruco_result)
    app.state.aruco.start()
    app.state.odometry.set_collision_plan(None, robot_radius_mm=settings.odometry_robot_radius_mm)

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
            _apply_plan_collision_constraints(loaded)
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
    _apply_plan_collision_constraints(plan)
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
    _apply_plan_collision_constraints(plan)
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
