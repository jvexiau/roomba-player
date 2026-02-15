# roomba-player v1.0.1

[Go directly to French version (FR)](#version-francaise)
[Session context / handover (no secrets)](docs/context.md)

## English

### Session Context

- Handover file (safe to share, no secrets): `docs/context.md`

### Overview

`roomba-player` is a FastAPI + web player platform to control and monitor a Roomba from a Raspberry Pi.

It includes:
- real-time control (`WS /ws/control`)
- real-time telemetry (`WS /ws/telemetry`)
- always-on camera pipeline (if enabled)
- ArUco detection + overlay + odometry snap (single marker mode)
- 2D map rendering and persisted odometry

### Main Features

- Live control
  - joystick
  - keyboard (`z q s d`)
  - hold-to-move / release-to-stop
- Live sensors/telemetry
  - battery, bumpers, cliffs, wall/dock, encoders, distance/angle
- Camera
  - always-on backend pipeline when enabled
  - `/camera/stream` serves latest in-memory frames
- ArUco
  - periodic detection (`ROOMBA_PLAYER_ARUCO_INTERVAL_SEC`, default `0.5`)
  - overlay on player camera
  - odometry correction from plan marker references
  - realtime logs per analysis frame: `FOUND` / `NOT_FOUND` + detailed marker metrics
- Odometry
  - encoder based (Roomba 760)
  - JSONL history (`bdd/odometry_history.jsonl`)
  - restore on startup
  - collision constraints against room/object geometry
- Ops
  - `make deploy-rpi`
  - `make restart-rpi`
  - `make stop-rpi`
  - `make logs-rpi`

### Architecture

- Backend: `src/roomba_player/*.py`
- Frontend: `src/roomba_player/web/*`
- Example plan: `examples/salon.yaml`
- Tests: `tests/*`
- RPi deploy script: `scripts/deploy_rpi.sh`

### Requirements

- Python `>=3.11`
- Main Python deps: `fastapi`, `uvicorn`, `websockets`, `pydantic`, `pydantic-settings`, `python-dotenv`, `PyYAML`, `pyserial`, `opencv-contrib-python-headless`
- Dev/RPi tools: `bash`, `ssh`, `rsync`, `make`
- Raspberry Pi binaries: `rpicam-vid`, `ffmpeg`

### Installation (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

### Run (local)

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

- Home: `http://<host>:8000/`
- Player: `http://<host>:8000/player`

### Raspberry Pi Deployment

Prepare:

```bash
cp .env.rpi.example .env.rpi
mkdir -p plans
cp examples/salon.yaml plans/salon.yaml
```

Minimum `.env.rpi` values:
- `RPI_HOST`, `RPI_USER`, `RPI_PORT`, `RPI_APP_DIR`
- `ROOMBA_SERIAL_PORT`, `ROOMBA_BAUDRATE`, `ROOMBA_TIMEOUT_SEC`
- `PLAN_DEFAULT_PATH` (example: `plans/salon.yaml`)

Commands:

```bash
make deploy-rpi
make restart-rpi
make stop-rpi
make logs-rpi
```

### Configuration Parameters

All backend env vars use `ROOMBA_PLAYER_` prefix.

General:
- `ROOMBA_PLAYER_SERVICE_NAME` (default: `roomba-player`)
- `ROOMBA_PLAYER_TELEMETRY_INTERVAL_SEC` (default: `0.1`)

Roomba/Serial:
- `ROOMBA_PLAYER_ROOMBA_SERIAL_PORT` (default: `/dev/ttyUSB0`)
- `ROOMBA_PLAYER_ROOMBA_BAUDRATE` (default: `115200`)
- `ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC` (default: `1.0`)

Camera:
- `ROOMBA_PLAYER_CAMERA_STREAM_ENABLED`
- `ROOMBA_PLAYER_CAMERA_WIDTH` (default: `800`)
- `ROOMBA_PLAYER_CAMERA_HEIGHT` (default: `600`)
- `ROOMBA_PLAYER_CAMERA_FRAMERATE` (default: `15`)
- `ROOMBA_PLAYER_CAMERA_PROFILE` (default: `high`)
- `ROOMBA_PLAYER_CAMERA_SHUTTER` (default: `12000`)
- `ROOMBA_PLAYER_CAMERA_DENOISE` (default: `cdn_fast`)
- `ROOMBA_PLAYER_CAMERA_SHARPNESS` (default: `1.1`)
- `ROOMBA_PLAYER_CAMERA_AWB` (default: `auto`)
- `ROOMBA_PLAYER_CAMERA_H264_TCP_PORT` (default: `9100`)
- `ROOMBA_PLAYER_CAMERA_HTTP_BIND_HOST` (default: `0.0.0.0`)
- `ROOMBA_PLAYER_CAMERA_HTTP_PORT` (default: `8081`)
- `ROOMBA_PLAYER_CAMERA_HTTP_PATH` (default: `/stream.mjpg`)

ArUco:
- `ROOMBA_PLAYER_ARUCO_ENABLED`
- `ROOMBA_PLAYER_ARUCO_INTERVAL_SEC` (default: `0.5`)
- `ROOMBA_PLAYER_ARUCO_DICTIONARY` (default: `DICT_4X4_50`)
- `ROOMBA_PLAYER_ARUCO_SNAP_ENABLED` (default: `true`)
- `ROOMBA_PLAYER_ARUCO_FOCAL_PX` (default: `900.0`)
- `ROOMBA_PLAYER_ARUCO_MARKER_SIZE_CM` (default: `15.0`)
- `ROOMBA_PLAYER_ARUCO_OVERLAY_FLIP_X` (default: `false`)
- `ROOMBA_PLAYER_ARUCO_POSE_BLEND` (default: `0.35`)
- `ROOMBA_PLAYER_ARUCO_THETA_BLEND` (default: `0.2`)
- `ROOMBA_PLAYER_ARUCO_HEADING_GAIN_DEG` (default: `8.0`)

Odometry:
- `ROOMBA_PLAYER_ODOMETRY_HISTORY_PATH` (default: `bdd/odometry_history.jsonl`)
- `ROOMBA_PLAYER_ODOMETRY_SOURCE` (default: `encoders`)
- `ROOMBA_PLAYER_ODOMETRY_MM_PER_TICK` (default: `0.445`)
- `ROOMBA_PLAYER_ODOMETRY_LINEAR_SCALE` (default: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ANGULAR_SCALE` (default: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ROBOT_RADIUS_MM` (default: `180.0`)
- `ROOMBA_PLAYER_ODOMETRY_COLLISION_MARGIN_SCALE` (default: `0.55`)

Plan:
- `ROOMBA_PLAYER_PLAN_DEFAULT_PATH`

### Plan Format

Required fields:
- `contour`
- `start_pose`
- `object_shapes`
- `objects`

Optional:
- `aruco_markers`

See: `examples/salon.yaml`

### API / WebSockets

HTTP:
- `GET /`
- `GET /player`
- `GET /health`
- `GET /telemetry`
- `POST /camera/start` (compat endpoint; camera is already auto-started when enabled)
- `GET /camera/stream`
- `GET /aruco/status`
- `GET /aruco/debug`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`

WebSocket:
- `WS /ws/telemetry`
- `WS /ws/control`

### Recommended Workflow

1. Load a plan (`plans/salon.yaml`).
2. Check start pose on map.
3. Open `/player` (camera auto-active if enabled).
4. Check telemetry and sensors.
5. Drive manually.
6. Check `GET /aruco/debug` for ArUco diagnostics.
7. If odometry drifts, use `reset-history + start pose`.

### Troubleshooting

ArUco overlay stale:
- check `GET /aruco/debug`
- verify camera pipeline is active

No ArUco detection:
- verify `ARUCO_DICTIONARY` matches printed markers
- verify `CAMERA_STREAM_ENABLED=true`
- increase camera resolution/light

Sensor stream appears frozen:
- check telemetry fields: `sensor_stream_alive`, `sensor_stream_last_update_age_sec`, `sensor_stream_restart_count`, `sensor_stream_last_error`

Collision too early/late:
- tune `ODOMETRY_ROBOT_RADIUS_MM`, `ODOMETRY_COLLISION_MARGIN_SCALE`

---

## Version Francaise

[Contexte de reprise de session (sans secrets)](docs/context.md)

### Contexte de session

- Fichier de reprise (partageable, sans secrets): `docs/context.md`

### Vue d'ensemble

`roomba-player` est une plateforme FastAPI + interface web `/player` pour piloter et monitorer un Roomba via Raspberry Pi.

Elle inclut:
- contrôle temps réel (`WS /ws/control`)
- télémétrie temps réel (`WS /ws/telemetry`)
- pipeline caméra always-on (si activée)
- détection ArUco + overlay + snap odométrique (mode mono marqueur)
- rendu plan 2D et odométrie persistée

### Fonctionnalités principales

- Contrôle live
  - joystick
  - clavier (`z q s d`)
  - hold-to-move / release-to-stop
- Capteurs/télémétrie live
  - batterie, bumpers, cliffs, wall/dock, encodeurs, distance/angle
- Caméra
  - pipeline backend always-on quand activée
  - `/camera/stream` sert les dernières frames en mémoire
- ArUco
  - détection périodique (`ROOMBA_PLAYER_ARUCO_INTERVAL_SEC`, défaut `0.5`)
  - overlay sur la caméra du player
  - correction odométrique depuis les marqueurs du plan
  - logs realtime par frame d’analyse: `FOUND` / `NOT_FOUND` + métriques détaillées
- Odométrie
  - basée sur encodeurs (Roomba 760)
  - historique JSONL (`bdd/odometry_history.jsonl`)
  - restauration au démarrage
  - contraintes de collision murs/objets
- Ops
  - `make deploy-rpi`
  - `make restart-rpi`
  - `make stop-rpi`
  - `make logs-rpi`

### Architecture

- Backend: `src/roomba_player/*.py`
- Frontend: `src/roomba_player/web/*`
- Plan exemple: `examples/salon.yaml`
- Tests: `tests/*`
- Déploiement RPi: `scripts/deploy_rpi.sh`

### Prérequis

- Python `>=3.11`
- Dépendances Python principales: `fastapi`, `uvicorn`, `websockets`, `pydantic`, `pydantic-settings`, `python-dotenv`, `PyYAML`, `pyserial`, `opencv-contrib-python-headless`
- Outils dev/RPi: `bash`, `ssh`, `rsync`, `make`
- Binaires Raspberry Pi: `rpicam-vid`, `ffmpeg`

### Installation locale

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

### Lancement local

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

- Home: `http://<host>:8000/`
- Player: `http://<host>:8000/player`

### Deploiement Raspberry Pi

Preparation:

```bash
cp .env.rpi.example .env.rpi
mkdir -p plans
cp examples/salon.yaml plans/salon.yaml
```

Minimum a renseigner dans `.env.rpi`:
- `RPI_HOST`, `RPI_USER`, `RPI_PORT`, `RPI_APP_DIR`
- `ROOMBA_SERIAL_PORT`, `ROOMBA_BAUDRATE`, `ROOMBA_TIMEOUT_SEC`
- `PLAN_DEFAULT_PATH` (ex: `plans/salon.yaml`)

Commandes:

```bash
make deploy-rpi
make restart-rpi
make stop-rpi
make logs-rpi
```

### Parametres de configuration

Tous les paramètres backend utilisent le préfixe `ROOMBA_PLAYER_`.

Generaux:
- `ROOMBA_PLAYER_SERVICE_NAME` (defaut: `roomba-player`)
- `ROOMBA_PLAYER_TELEMETRY_INTERVAL_SEC` (defaut: `0.1`)

Roomba/Serie:
- `ROOMBA_PLAYER_ROOMBA_SERIAL_PORT` (defaut: `/dev/ttyUSB0`)
- `ROOMBA_PLAYER_ROOMBA_BAUDRATE` (defaut: `115200`)
- `ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC` (defaut: `1.0`)

Camera:
- `ROOMBA_PLAYER_CAMERA_STREAM_ENABLED`
- `ROOMBA_PLAYER_CAMERA_WIDTH` (defaut: `800`)
- `ROOMBA_PLAYER_CAMERA_HEIGHT` (defaut: `600`)
- `ROOMBA_PLAYER_CAMERA_FRAMERATE` (defaut: `15`)
- `ROOMBA_PLAYER_CAMERA_PROFILE` (defaut: `high`)
- `ROOMBA_PLAYER_CAMERA_SHUTTER` (defaut: `12000`)
- `ROOMBA_PLAYER_CAMERA_DENOISE` (defaut: `cdn_fast`)
- `ROOMBA_PLAYER_CAMERA_SHARPNESS` (defaut: `1.1`)
- `ROOMBA_PLAYER_CAMERA_AWB` (defaut: `auto`)
- `ROOMBA_PLAYER_CAMERA_H264_TCP_PORT` (defaut: `9100`)
- `ROOMBA_PLAYER_CAMERA_HTTP_BIND_HOST` (defaut: `0.0.0.0`)
- `ROOMBA_PLAYER_CAMERA_HTTP_PORT` (defaut: `8081`)
- `ROOMBA_PLAYER_CAMERA_HTTP_PATH` (defaut: `/stream.mjpg`)

ArUco:
- `ROOMBA_PLAYER_ARUCO_ENABLED`
- `ROOMBA_PLAYER_ARUCO_INTERVAL_SEC` (defaut: `0.5`)
- `ROOMBA_PLAYER_ARUCO_DICTIONARY` (defaut: `DICT_4X4_50`)
- `ROOMBA_PLAYER_ARUCO_SNAP_ENABLED` (defaut: `true`)
- `ROOMBA_PLAYER_ARUCO_FOCAL_PX` (defaut: `900.0`)
- `ROOMBA_PLAYER_ARUCO_MARKER_SIZE_CM` (defaut: `15.0`)
- `ROOMBA_PLAYER_ARUCO_OVERLAY_FLIP_X` (defaut: `false`)
- `ROOMBA_PLAYER_ARUCO_POSE_BLEND` (defaut: `0.35`)
- `ROOMBA_PLAYER_ARUCO_THETA_BLEND` (defaut: `0.2`)
- `ROOMBA_PLAYER_ARUCO_HEADING_GAIN_DEG` (defaut: `8.0`)

Odometrie:
- `ROOMBA_PLAYER_ODOMETRY_HISTORY_PATH` (defaut: `bdd/odometry_history.jsonl`)
- `ROOMBA_PLAYER_ODOMETRY_SOURCE` (defaut: `encoders`)
- `ROOMBA_PLAYER_ODOMETRY_MM_PER_TICK` (defaut: `0.445`)
- `ROOMBA_PLAYER_ODOMETRY_LINEAR_SCALE` (defaut: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ANGULAR_SCALE` (defaut: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ROBOT_RADIUS_MM` (defaut: `180.0`)
- `ROOMBA_PLAYER_ODOMETRY_COLLISION_MARGIN_SCALE` (defaut: `0.55`)

Plan:
- `ROOMBA_PLAYER_PLAN_DEFAULT_PATH`

### Format des plans

Champs requis:
- `contour`
- `start_pose`
- `object_shapes`
- `objects`

Optionnel:
- `aruco_markers`

Voir: `examples/salon.yaml`

### API / WebSockets

HTTP:
- `GET /`
- `GET /player`
- `GET /health`
- `GET /telemetry`
- `POST /camera/start` (endpoint de compatibilite; la camera est deja auto-demarree si activee)
- `GET /camera/stream`
- `GET /aruco/status`
- `GET /aruco/debug`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`

WebSocket:
- `WS /ws/telemetry`
- `WS /ws/control`

### Workflow recommande

1. Charger un plan (`plans/salon.yaml`).
2. Verifier la pose start sur la map.
3. Ouvrir `/player` (camera active automatiquement si activee).
4. Verifier telemetry/capteurs.
5. Piloter manuellement.
6. Verifier `GET /aruco/debug` pour le diagnostic ArUco.
7. En cas de derive odometrique, utiliser `reset-history + start pose`.

### Depannage

Overlay ArUco stale:
- verifier `GET /aruco/debug`
- verifier pipeline camera actif

Pas de detection ArUco:
- verifier `ARUCO_DICTIONARY`
- verifier `CAMERA_STREAM_ENABLED=true`
- augmenter resolution/lumiere

Capteurs figes:
- verifier `sensor_stream_alive`, `sensor_stream_last_update_age_sec`, `sensor_stream_restart_count`, `sensor_stream_last_error`

Collision trop tot/tard:
- ajuster `ODOMETRY_ROBOT_RADIUS_MM`, `ODOMETRY_COLLISION_MARGIN_SCALE`

## License

MIT
