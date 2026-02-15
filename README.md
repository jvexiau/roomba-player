# roomba-player v0.6.0

> **FR**: Plateforme Python pour piloter et monitorer un Roomba via Raspberry Pi, avec interface web temps réel, caméra optionnelle, plan du salon et odométrie persistée.
>
> **EN**: Python platform to control and monitor a Roomba via Raspberry Pi, with real-time web UI, optional camera stream, room plan, and persisted odometry.

## Project provenance / Provenance du code

**FR**: Ce programme est développé uniquement avec Codex, sans intervention humaine directe dans l'écriture du code.

**EN**: This program is developed only with Codex, with no direct human intervention in code writing.

## Features

- Modular frontend (HTML/CSS/JS separated from Python):
  - `src/roomba_player/web/home.html`
  - `src/roomba_player/web/player.html`
  - `src/roomba_player/web/static/home.css`
  - `src/roomba_player/web/static/player.css`
  - `src/roomba_player/web/static/player-*.js`
- Cache busting on static assets (`?v=<hash>`) for automatic browser refresh
- Player UI in dark mode
- Real-time control page `/player`:
  - joystick buttons
  - AZERTY keyboard (`z q s d`)
  - hold-to-move, release-to-stop
  - live command log
- Real-time telemetry via `WS /ws/telemetry`
- Control protocol via `WS /ws/control`
- Bumper safety guard (frontend + backend):
  - no forced reverse
  - forward blocked when bumper constraints are active
- Camera stream (optional): `rpicam-vid` + `ffmpeg` -> `/camera/stream`
- ArUco detection overlay (optional): backend detection every second on camera stream + passive frontend overlay from websocket telemetry
- Plan loading (`JSON`/`YAML`) and map rendering
- Odometry based on wheel encoders (Roomba 760 strategy), persisted in JSONL
- Last pose restore at startup
- History reset + reposition to plan start pose (`/api/odometry/reset-history`)

## Requirements / Prérequis

### Python modules

Installed with `pip install -e .`:
- `fastapi`
- `uvicorn`
- `websockets`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `PyYAML`
- `pyserial`
- `opencv-contrib-python-headless`

Dev tools:
- `pytest`
- `httpx`
- `ruff`

### System tools (PC)

- `ssh`
- `rsync`
- `bash`
- `make`

### System tools (Raspberry Pi)

- `rpicam-vid`
- `ffmpeg`

## Local run (optional) / Lancement local (optionnel)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

## Plans and map / Plans et carte

- Runtime plans are stored in `plans/` (ignored by git).
- Example plan is tracked: `examples/salon.yaml`.
- Plan APIs:
  - `GET /api/plan`
  - `POST /api/plan/load-file` with `{"path":"plans/salon.yaml"}`
  - `POST /api/plan/load-json` with a full plan payload

Expected top-level plan fields:
- `unit`
- `contour`
- `start_pose`
- `object_shapes`
- `objects`
- `aruco_markers` (optional)

## Odometry and history / Odométrie et historique

- Default odometry source: wheel encoders (`left_encoder_counts`, `right_encoder_counts`)
- History file: `bdd/odometry_history.jsonl` (append-only)
- Last pose is restored at startup if history exists
- API:
  - `GET /api/odometry`
  - `POST /api/odometry/reset`
  - `POST /api/odometry/reset-history` (clear history + reset to current plan `start_pose`)

## Deploy to Raspberry Pi / Déploiement Raspberry Pi

### 1) Configure deployment

```bash
cp .env.rpi.example .env.rpi
mkdir -p plans
cp examples/salon.yaml plans/salon.yaml
```

Set at least in `.env.rpi`:
- `RPI_HOST`
- `RPI_USER`
- `RPI_PORT`
- `RPI_APP_DIR`
- `ROOMBA_SERIAL_PORT`
- `ROOMBA_BAUDRATE`
- `ROOMBA_TIMEOUT_SEC`
- `PLAN_DEFAULT_PATH` (recommended: `plans/salon.yaml`)
- `CAMERA_STREAM_ENABLED` (`true` or `false`)
- `ARUCO_ENABLED` (`true` or `false`)
- `ARUCO_INTERVAL_SEC` (default `1.0`)
- `ARUCO_DICTIONARY` (default `DICT_4X4_50`)
- `ARUCO_SNAP_ENABLED` (default `true`, applies odometry correction from detected markers)
- `ARUCO_FOCAL_PX` (default `900.0`, used with marker size to estimate distance)
- `ARUCO_POSE_BLEND` (default `0.35`, position blend factor for ArUco correction)
- `ARUCO_THETA_BLEND` (default `0.2`, heading blend factor for ArUco correction)
- `ARUCO_HEADING_GAIN_DEG` (default `8.0`, small heading offset from marker image offset)
- `ODOMETRY_HISTORY_PATH` (default: `bdd/odometry_history.jsonl`)
- `ODOMETRY_SOURCE` (default: `encoders`)
- `ODOMETRY_MM_PER_TICK` (default: `0.445`)
- `ODOMETRY_ROBOT_RADIUS_MM` (default: `180.0`, used to clamp odometry near walls/objects)

### 2) Deploy and restart

```bash
make deploy-rpi
```

### 3) Optional dependency upgrade

```bash
make update-rpi
```

### 4) Logs / restart only

```bash
make logs-rpi
make restart-rpi
```

## Endpoints summary

- `GET /`
- `GET /player`
- `GET /health`
- `GET /telemetry`
- `POST /camera/start`
- `GET /camera/stream`
- `GET /aruco/status`
- `GET /aruco/debug`
- `WS /ws/telemetry`
- `WS /ws/control`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`

## ArUco notes / Notes ArUco

- The ArUco detector is fed from `/camera/stream` frames. If no active stream client exists (for example `/player` closed), detections will stop.
- `ARUCO_DICTIONARY` must match your printed markers exactly. Invalid values now return an explicit `unsupported_dictionary:<name>` reason in `/aruco/debug`.
- Supported dictionaries include:
  - `DICT_4X4_50`, `DICT_4X4_100`, `DICT_4X4_250`, `DICT_4X4_1000`
  - `DICT_5X5_50`, `DICT_5X5_100`, `DICT_5X5_250`, `DICT_5X5_1000`
  - `DICT_6X6_50`, `DICT_6X6_100`, `DICT_6X6_250`, `DICT_6X6_1000`
  - `DICT_7X7_50`, `DICT_7X7_100`, `DICT_7X7_250`, `DICT_7X7_1000`
  - `DICT_ARUCO_ORIGINAL`
  - `DICT_APRILTAG_16h5`, `DICT_APRILTAG_25h9`, `DICT_APRILTAG_36h10`, `DICT_APRILTAG_36h11`
- If you need longer-range detection, prefer higher camera resolution (`1280x720`) and enough light before increasing framerate.

## Notes

- Runtime plans are stored in `plans/` (git ignored).
- Runtime history is stored in `bdd/` (git ignored).
- This project is developed iteratively with Codex.

## License

MIT
