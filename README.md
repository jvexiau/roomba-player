# roomba-player v0.6.0

> **FR**: Plateforme Python pour piloter et monitorer un Roomba via Raspberry Pi, avec interface web temps réel, caméra optionnelle, détection ArUco, plan 2D et odométrie persistée.
>
> **EN**: Python platform to control and monitor a Roomba via Raspberry Pi, with real-time web UI, optional camera stream, ArUco detection, 2D plan and persisted odometry.

## Sommaire

- [1. Vue d'ensemble](#1-vue-densemble)
- [2. Fonctionnalités](#2-fonctionnalités)
- [3. Architecture rapide](#3-architecture-rapide)
- [4. Requirements / Prérequis](#4-requirements--prérequis)
- [5. Installation locale](#5-installation-locale)
- [6. Usage local](#6-usage-local)
- [7. Déploiement Raspberry Pi](#7-déploiement-raspberry-pi)
- [8. Paramètres de configuration](#8-paramètres-de-configuration)
- [9. Format des plans](#9-format-des-plans)
- [10. Endpoints et WebSockets](#10-endpoints-et-websockets)
- [11. Workflow recommandé](#11-workflow-recommandé)
- [12. Troubleshooting](#12-troubleshooting)
- [13. License](#13-license)

## 1. Vue d'ensemble

`roomba-player` expose une API FastAPI + une UI web `/player` pour:

- piloter un Roomba (drive/modes/dock)
- visualiser la télémétrie live
- afficher un plan 2D du salon
- maintenir une odométrie persistée et contrainte par collision (murs + objets)
- corriger la pose via ArUco (snap odométrique)

## 2. Fonctionnalités

- Contrôle temps réel (`WS /ws/control`)
  - joystick
  - clavier AZERTY (`z q s d`)
  - hold-to-move / release-to-stop
- Télémétrie live (`WS /ws/telemetry`)
  - batterie, bumpers, cliffs, wall/dock, encodeurs, distance/angle
- Caméra (optionnelle)
  - pipeline `rpicam-vid -> ffmpeg -> /camera/stream`
- ArUco (optionnel)
  - détection backend périodique depuis le stream
  - overlay frontend
  - snap odométrique depuis `aruco_markers` du plan
- Odométrie
  - source encodeurs (Roomba 760)
  - historique JSONL (`bdd/odometry_history.jsonl`)
  - restauration auto au démarrage
  - collision planifiée (anti traversée murs/objets)
  - glissement tangent renforcé le long des obstacles
- Plan
  - chargement JSON/YAML
  - rendu map + objets + IDs ArUco
  - reset historique + repositionnement sur start pose
- Ops
  - `make deploy-rpi`, `make restart-rpi`, `make stop`, `make logs-rpi`

## 3. Architecture rapide

- Backend: `src/roomba_player/*.py`
- Frontend: `src/roomba_player/web/*`
- Plan exemple: `examples/salon.yaml`
- Tests: `tests/*`
- Déploiement: `scripts/deploy_rpi.sh`

## 4. Requirements / Prérequis

### Python

- Python `>=3.11`
- Dépendances principales:
  - `fastapi`
  - `uvicorn`
  - `websockets`
  - `pydantic`, `pydantic-settings`
  - `python-dotenv`
  - `PyYAML`
  - `pyserial`
  - `opencv-contrib-python-headless`

### Outils système (poste de dev)

- `bash`
- `ssh`
- `rsync`
- `make`

### Outils système (Raspberry Pi)

- `rpicam-vid`
- `ffmpeg`

## 5. Installation locale

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

## 6. Usage local

Démarrage:

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

UI:

- Home: `http://<host>:8000/`
- Player: `http://<host>:8000/player`

## 7. Déploiement Raspberry Pi

### 7.1 Préparer la config

```bash
cp .env.rpi.example .env.rpi
mkdir -p plans
cp examples/salon.yaml plans/salon.yaml
```

Renseigner au minimum dans `.env.rpi`:

- `RPI_HOST`, `RPI_USER`, `RPI_PORT`, `RPI_APP_DIR`
- `ROOMBA_SERIAL_PORT`, `ROOMBA_BAUDRATE`, `ROOMBA_TIMEOUT_SEC`
- `PLAN_DEFAULT_PATH` (ex: `plans/salon.yaml`)

### 7.2 Déployer

```bash
make deploy-rpi
```

### 7.3 Redémarrer sans resync

```bash
make restart-rpi
```

### 7.4 Stopper le service

```bash
make stop
```

### 7.5 Suivre les logs

```bash
make logs-rpi
```

## 8. Paramètres de configuration

Tous les paramètres backend utilisent le préfixe `ROOMBA_PLAYER_`.

### 8.1 Paramètres généraux

- `ROOMBA_PLAYER_SERVICE_NAME` (default: `roomba-player`)
- `ROOMBA_PLAYER_TELEMETRY_INTERVAL_SEC` (default: `0.1`)

### 8.2 Roomba / série

- `ROOMBA_PLAYER_ROOMBA_SERIAL_PORT` (default: `/dev/ttyUSB0`)
- `ROOMBA_PLAYER_ROOMBA_BAUDRATE` (default: `115200`)
- `ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC` (default: `1.0`)

### 8.3 Caméra

- `ROOMBA_PLAYER_CAMERA_STREAM_ENABLED` (`true`/`false`)
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

### 8.4 ArUco

- `ROOMBA_PLAYER_ARUCO_ENABLED` (`true`/`false`)
- `ROOMBA_PLAYER_ARUCO_INTERVAL_SEC` (default: `1.0`)
- `ROOMBA_PLAYER_ARUCO_DICTIONARY` (default: `DICT_4X4_50`)
- `ROOMBA_PLAYER_ARUCO_SNAP_ENABLED` (default: `true`)
- `ROOMBA_PLAYER_ARUCO_FOCAL_PX` (default: `900.0`)
- `ROOMBA_PLAYER_ARUCO_POSE_BLEND` (default: `0.35`)
- `ROOMBA_PLAYER_ARUCO_THETA_BLEND` (default: `0.2`)
- `ROOMBA_PLAYER_ARUCO_HEADING_GAIN_DEG` (default: `8.0`)

ArUco supportés:

- `DICT_4X4_50`, `DICT_4X4_100`, `DICT_4X4_250`, `DICT_4X4_1000`
- `DICT_5X5_50`, `DICT_5X5_100`, `DICT_5X5_250`, `DICT_5X5_1000`
- `DICT_6X6_50`, `DICT_6X6_100`, `DICT_6X6_250`, `DICT_6X6_1000`
- `DICT_7X7_50`, `DICT_7X7_100`, `DICT_7X7_250`, `DICT_7X7_1000`
- `DICT_ARUCO_ORIGINAL`
- `DICT_APRILTAG_16h5`, `DICT_APRILTAG_25h9`, `DICT_APRILTAG_36h10`, `DICT_APRILTAG_36h11`

### 8.5 Odométrie

- `ROOMBA_PLAYER_ODOMETRY_HISTORY_PATH` (default: `bdd/odometry_history.jsonl`)
- `ROOMBA_PLAYER_ODOMETRY_SOURCE` (default: `encoders`)
- `ROOMBA_PLAYER_ODOMETRY_MM_PER_TICK` (default: `0.445`)
- `ROOMBA_PLAYER_ODOMETRY_LINEAR_SCALE` (default: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ANGULAR_SCALE` (default: `1.0`)
- `ROOMBA_PLAYER_ODOMETRY_ROBOT_RADIUS_MM` (default: `180.0`)
- `ROOMBA_PLAYER_ODOMETRY_COLLISION_MARGIN_SCALE` (default: `0.55`)

### 8.6 Plan par défaut

- `ROOMBA_PLAYER_PLAN_DEFAULT_PATH` (default: empty)

## 9. Format des plans

Un plan doit au minimum contenir:

- `contour`: polygone pièce
- `start_pose`
- `object_shapes`
- `objects`

Optionnel:

- `aruco_markers` pour snap odométrique depuis ArUco

Exemple complet: `examples/salon.yaml`.

## 10. Endpoints et WebSockets

### HTTP

- `GET /`
- `GET /player`
- `GET /health`
- `GET /telemetry`
- `POST /camera/start`
- `GET /camera/stream`
- `GET /aruco/status`
- `GET /aruco/debug`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`

### WebSocket

- `WS /ws/telemetry`
- `WS /ws/control`

## 11. Workflow recommandé

1. Charger un plan (`plans/salon.yaml`).
2. Vérifier la pose start sur la map.
3. Démarrer le stream caméra si utilisé.
4. Vérifier la télémétrie live et les capteurs.
5. Piloter en mode manuel.
6. Contrôler `GET /aruco/debug` si snap ArUco utilisé.
7. Si dérive odométrique, utiliser `reset-history + start pose`.

## 12. Troubleshooting

### ArUco détecté mais overlay reste affiché

- Le backend marque désormais les résultats périmés (`stale`) et l’overlay est effacé.
- Vérifier `GET /aruco/debug`.

### ArUco ne détecte rien

- Vérifier dictionnaire (`ARUCO_DICTIONARY`) vs markers imprimés.
- Vérifier que `/camera/stream` est actif.
- Augmenter résolution caméra (`1280x720`) + lumière.

### Capteurs figés

- Le watchdog stream capteur est auto-restart.
- Vérifier dans la télémétrie:
  - `sensor_stream_alive`
  - `sensor_stream_last_update_age_sec`
  - `sensor_stream_restart_count`
  - `sensor_stream_last_error`

### Collision trop tôt / trop tard

- Ajuster:
  - `ODOMETRY_ROBOT_RADIUS_MM`
  - `ODOMETRY_COLLISION_MARGIN_SCALE`

## 13. License

MIT
