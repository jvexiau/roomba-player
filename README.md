# roomba-player v0.2.0

> **FR**: Plateforme Python pour piloter et monitorer un Roomba via Raspberry Pi, avec interface web temps réel, caméra optionnelle, plan du salon et odométrie persistée.
>
> **EN**: Python platform to control and monitor a Roomba via Raspberry Pi, with real-time web UI, optional camera stream, room plan, and persisted odometry.

## Project provenance / Provenance du code

**FR**: Ce programme est développé uniquement avec Codex, sans intervention humaine directe dans l'écriture du code.

**EN**: This program is developed only with Codex, with no direct human intervention in code writing.

## Features

- Web assets split by responsibility:
  - `src/roomba_player/web/home.html`
  - `src/roomba_player/web/player.html`
  - `src/roomba_player/web/static/*.css`
  - `src/roomba_player/web/static/*.js`
- Static assets served with cache-busting hash query (`?v=<hash>`).
- Web control page: `/player` (joystick + clavier AZERTY `zqsd`)
- Real-time sensors via `WS /ws/telemetry`
- Control protocol via `WS /ws/control`
- Camera stream (optional): `rpicam-vid` + `ffmpeg` -> `/camera/stream`
- Plan loading (`JSON`/`YAML`) and map rendering
- Odometry from wheel encoders (Roomba 760 friendly)
- Odometry history persisted in `bdd/odometry_history.jsonl`
- Last known pose restored on service restart
- Reset history + reset pose to plan start from `/player`

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
- `ODOMETRY_HISTORY_PATH` (default: `bdd/odometry_history.jsonl`)

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
- `WS /ws/telemetry`
- `WS /ws/control`
- `GET /api/plan`
- `POST /api/plan/load-file`
- `POST /api/plan/load-json`
- `GET /api/odometry`
- `POST /api/odometry/reset`
- `POST /api/odometry/reset-history`

## License

MIT
