# Context / Handover (No Secrets)

Last update: 2026-02-15

## Purpose
This file is the project handover to resume work quickly after leaving Codex.
It is intentionally technical and secret-free.

Rules:
- never store credentials/tokens/private hostnames here
- never store personal shell history or local machine paths outside this repo
- prefer repo-relative commands and paths
- keep this file updated at each meaningful code/doc/behavior change so session resume stays coherent

## Project Snapshot
- Name: `roomba-player`
- Stack: FastAPI backend + vanilla web frontend (`/player`)
- Runtime target: Raspberry Pi + Roomba 760 (Open Interface)
- Core capabilities:
  - WS control (`/ws/control`)
  - WS telemetry (`/ws/telemetry`)
  - camera stream (`/camera/stream`)
  - ArUco detection and overlay
  - odometry with collision constraints from plan geometry
  - odometry persistence (`bdd/odometry_history.jsonl`)

## High-Level Architecture
- Transport/API: `src/roomba_player/app.py`, `src/roomba_player/ws.py`
- Robot adapter: `src/roomba_player/roomba.py`
- Camera pipeline: `src/roomba_player/camera.py`
- ArUco worker: `src/roomba_player/aruco.py`
- Odometry/collision: `src/roomba_player/odometry.py`
- Plan loading/validation: `src/roomba_player/plan.py`
- History persistence: `src/roomba_player/history.py`
- Frontend player: `src/roomba_player/web/*`

## Runtime Flows
### Control
1. Browser opens `WS /ws/control`.
2. `init` command connects Roomba, sets mode, starts sensor stream.
3. `drive/stop/clean/dock` commands are forwarded to OI.
4. Forward motion is guarded by bumper state in `ws.py`.

### Telemetry
1. Browser opens `WS /ws/telemetry`.
2. Server periodically sends snapshot every `ROOMBA_PLAYER_TELEMETRY_INTERVAL_SEC`.
3. Payload includes:
  - Roomba telemetry
  - odometry pose
  - ArUco status/result (`payload.aruco`)
4. Server tries self-healing sensor stream restarts (`ensure_sensor_stream`).

### Camera + ArUco
1. If camera is enabled, startup initializes camera pipeline and reader thread.
2. Reader loop keeps latest JPEG frame in memory.
3. ArUco worker receives frames at configured interval (default 0.5s).
4. Detection result is exposed via:
  - `/aruco/status`
  - `/aruco/debug`
  - telemetry websocket payload (`aruco` key)
5. On valid detection, odometry can snap toward marker-based target pose.

## API Surface (Current)
Defined in `src/roomba_player/app.py`:
- `GET /`
- `GET /player`
- `POST /camera/start` (compat endpoint)
- `GET /camera/stream`
- `GET /aruco/status`
- `GET /aruco/debug`
- `GET /health`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`
- `GET /telemetry`
- `WS /ws/telemetry`
- `WS /ws/control`

Documentation rule:
- before editing README endpoints, verify against `app.py` route decorators

## Configuration Map (env prefix `ROOMBA_PLAYER_`)
Source: `src/roomba_player/config.py`

Core:
- `SERVICE_NAME`
- `TELEMETRY_INTERVAL_SEC` (default `0.1`)

Roomba:
- `ROOMBA_SERIAL_PORT` (default `/dev/ttyUSB0`)
- `ROOMBA_BAUDRATE` (default `115200`)
- `ROOMBA_TIMEOUT_SEC` (default `1.0`)

Camera:
- `CAMERA_STREAM_ENABLED` (default `false`)
- `CAMERA_WIDTH` (default `800`)
- `CAMERA_HEIGHT` (default `600`)
- `CAMERA_FRAMERATE` (default `15`)
- `CAMERA_PROFILE` (default `high`)
- `CAMERA_SHUTTER` (default `12000`)
- `CAMERA_DENOISE` (default `cdn_fast`)
- `CAMERA_SHARPNESS` (default `1.1`)
- `CAMERA_AWB` (default `auto`)
- `CAMERA_H264_TCP_PORT` (default `9100`)
- `CAMERA_HTTP_BIND_HOST` (default `0.0.0.0`)
- `CAMERA_HTTP_PORT` (default `8081`)
- `CAMERA_HTTP_PATH` (default `/stream.mjpg`)

ArUco:
- `ARUCO_ENABLED` (default `false`)
- `ARUCO_INTERVAL_SEC` (default `0.5`)
- `ARUCO_DICTIONARY` (default `DICT_4X4_50`)
- `ARUCO_SNAP_ENABLED` (default `true`)
- `ARUCO_FOCAL_PX` (default `900.0`)
- `ARUCO_MARKER_SIZE_CM` (default `15.0`)
- `ARUCO_OVERLAY_FLIP_X` (default `false`)
- `ARUCO_POSE_BLEND` (default `0.35`)
- `ARUCO_THETA_BLEND` (default `0.2`)
- `ARUCO_HEADING_GAIN_DEG` (default `8.0`)

Plan/Odometry:
- `PLAN_DEFAULT_PATH`
- `ODOMETRY_HISTORY_PATH` (default `bdd/odometry_history.jsonl`)
- `ODOMETRY_SOURCE` (default `encoders`)
- `ODOMETRY_MM_PER_TICK` (default `0.445`)
- `ODOMETRY_LINEAR_SCALE` (default `1.0`)
- `ODOMETRY_ANGULAR_SCALE` (default `1.0`)
- `ODOMETRY_ROBOT_RADIUS_MM` (default `180.0`)
- `ODOMETRY_COLLISION_MARGIN_SCALE` (default `0.55` via settings)

## Frontend Modules (Player)
- bootstrap/state: `src/roomba_player/web/static/player-main.js`, `player-state.js`
- camera load/retry: `src/roomba_player/web/static/player-camera.js`
- ArUco overlay draw/update: `src/roomba_player/web/static/player-aruco.js`
- map render + robot cursor: `src/roomba_player/web/static/player-map.js`
- controls/joystick/ui wiring: `src/roomba_player/web/static/player-controls.js`
- telemetry rendering: `src/roomba_player/web/static/player-telemetry.js`

## Testing & Validation
### Standard
- `pytest -q`

### Targeted
- `pytest -q tests/test_odometry.py`
- `pytest -q tests/test_aruco_snap.py`
- `pytest -q tests/test_roomba_stream.py`
- `pytest -q tests/test_ws_control.py`

### Smoke checks after behavior changes
- open `/player`, verify camera appears on first load
- verify ArUco overlay disappears quickly after marker loss
- verify odometry moves and does not cross walls/objects
- verify bumper guard blocks forward motion immediately

## Operations (Make)
- `make deploy-rpi`
- `make update-rpi`
- `make restart-rpi`
- `make stop-rpi`
- `make logs-rpi`

Scripts:
- `scripts/deploy_rpi.sh`
- `scripts/stop_rpi.sh`

## Known Sensitive Areas
- Odometry collision behavior is highly sensitive to:
  - robot radius
  - collision margin scale
  - tangent/sliding clamp logic
- ArUco snap behavior is sensitive to:
  - marker area-to-distance mapping
  - inferred shape/yaw from corners
  - plan marker axis (`theta_deg`, `snap_pose`, `front_offset_mm`)
- Camera/ArUco stability is sensitive to:
  - frame decode throughput
  - detection interval
  - stale thresholds and reader thread health

## Known Gotchas
- `app.py` FastAPI metadata version may lag package version if not updated explicitly.
- `POST /camera/start` still exists as a compatibility route even with always-on camera logic.
- Default constructor value in `OdometryEstimator` can affect direct-instantiation tests if changed.
- Overlay accuracy requires consistent frame geometry assumptions between backend detection and frontend rendering.

## Quick Debug Runbook
### Camera missing
1. Check `ROOMBA_PLAYER_CAMERA_STREAM_ENABLED=true`
2. Check binaries on Pi: `rpicam-vid`, `ffmpeg`
3. Hit `/camera/stream` directly
4. Check server log around camera reader loop restart

### ArUco stale/off unexpectedly
1. Check `/aruco/debug` (`worker_alive`, `last_result_age_sec`, `last_frame_age_sec`)
2. Verify camera reader is producing frames
3. Verify dictionary matches printed markers
4. Validate detection cadence against `ARUCO_INTERVAL_SEC`

### Overlay offset
1. Verify configured stream size and real rendered size
2. Verify overlay canvas resize on image load and window resize
3. Verify no unintended mirroring (`ARUCO_OVERLAY_FLIP_X`)
4. Compare marker corners in debug payload vs drawn polygon

### Odometry frozen or unrealistic
1. Check telemetry includes encoder counts
2. Check bumpers not continuously active
3. Check collision constraints and start pose validity
4. Try `POST /api/odometry/reset-history` then verify updates resume

## Release/Doc Hygiene Checklist
Before commit/tag/push:
1. `git status --short`
2. `pytest -q`
3. Verify API list in `README.md` matches `app.py`
4. Verify version consistency across:
   - `README.md`
   - `pyproject.toml`
   - release/tag naming
5. Add changelog-style commit message (clear scope)

## Resume Checklist (Next Session)
1. Read this file (`docs/context.md`)
2. `git status --short`
3. `pytest -q`
4. Validate current routes in `src/roomba_player/app.py`
5. Validate live behavior on `/player` (camera + telemetry + map + ArUco)
6. Continue from latest open issue, then commit in small scopes
