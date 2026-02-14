# roomba-player

> **FR**: Plateforme Python pour piloter, visualiser, monitorer et auto-piloter un Roomba via Raspberry Pi.
>
> **EN**: Python platform to control, visualize, monitor, and auto-drive a Roomba through a Raspberry Pi.

## Vision / Vision

**FR**
- Construire une base robuste et performante pour le pilotage temps réel d'un Roomba.
- Exposer une API HTTP + WebSocket pour le contrôle, la télémétrie et le streaming d'état.
- Ajouter progressivement des capacités d'auto-pilotage avec sécurité et observabilité.

**EN**
- Build a robust and efficient foundation for real-time Roomba control.
- Expose an HTTP + WebSocket API for control, telemetry, and state streaming.
- Iteratively add autonomous driving capabilities with safety and observability.

## Project status / Etat du projet

**FR**: v0.3 initialisée: pilotage WebSocket + workflow de déploiement distant PC -> Raspberry Pi.

**EN**: v0.3 initialized: WebSocket control + remote deployment workflow from PC to Raspberry Pi.

## Project provenance / Provenance du code

**FR**: Ce programme est développé uniquement avec Codex, sans intervention humaine directe dans l'écriture du code.

**EN**: This program is developed only with Codex, with no direct human intervention in code writing.

## Python modules required by iteration / Modules Python requis par itération

### Iteration v0.1 (scaffold API)

**FR/EN**
- `fastapi`
- `uvicorn`
- `pydantic`
- `pytest` (dev)
- `httpx` (dev)
- `ruff` (dev)

Install / Installation:

```bash
pip install -e .[dev]
```

### Iteration v0.2 (USB serial control)

**Added / Ajoutés**
- `pyserial` (Roomba Open Interface over USB serial)
- `pydantic-settings` (environment-driven config)

Install / Installation:

```bash
pip install -e .[dev]
```

### Iteration v0.3 (remote dev/deploy workflow)

**Python modules**
- No new application module.
- Raspberry Pi still installs project dependencies with:

```bash
pip install -e .
```

**System tools (non-Python)**
- `ssh`
- `rsync`
- `bash`

## Hardware assumptions (v0.2)

**FR**
- Raspberry Pi connecté au Roomba via adaptateur USB vers pin OI.
- Device Linux typique: `/dev/ttyUSB0` (ou `/dev/ttyACM0` selon adaptateur).

**EN**
- Raspberry Pi connected to Roomba through USB to OI pin adapter.
- Typical Linux device: `/dev/ttyUSB0` (or `/dev/ttyACM0` depending on adapter).

## Repository layout / Structure

```text
.
├── .github/workflows/ci.yml
├── .env.example
├── .env.rpi.example
├── docs/architecture.md
├── scripts/deploy_rpi.sh
├── src/roomba_player/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── roomba.py
│   ├── telemetry.py
│   └── ws.py
├── tests/test_health.py
├── Makefile
├── .gitignore
├── pyproject.toml
└── README.md
```

## Quick start / Démarrage rapide

### 1) Create environment / Créer l'environnement

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2) Create env file (not committed) / Créer le fichier env (non versionné)

```bash
cp .env.example .env
```

`src/roomba_player/config.py` loads `.env` automatically.

### 3) Configure serial device / Configurer le port série

```bash
cat >> .env <<'EOF'
ROOMBA_PLAYER_ROOMBA_SERIAL_PORT=/dev/ttyUSB0
ROOMBA_PLAYER_ROOMBA_BAUDRATE=115200
EOF
```

### 4) Run API / Lancer l'API

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

### 5) Smoke check / Vérification

```bash
curl http://localhost:8000/health
```

Expected response / Réponse attendue:

```json
{"status":"ok","service":"roomba-player"}
```

## Remote development and deployment (PC -> Raspberry Pi)

### Preconditions / Prérequis

**FR**
- Développement local sur PC.
- Accès SSH au Raspberry Pi.
- `ssh` et `rsync` installés sur le PC.
- Python 3 installé sur le Raspberry Pi.

**EN**
- Local development on your PC.
- SSH access to Raspberry Pi.
- `ssh` and `rsync` installed on your PC.
- Python 3 installed on Raspberry Pi.

### Environment variables / Variables d'environnement

Location:
- Local runtime file: `.env` (ignored by Git)
- Local deploy file: `.env.rpi` (ignored by Git)
- Templates committed in repo: `.env.example`, `.env.rpi.example`

Setup:

```bash
cp .env.rpi.example .env.rpi
```

- `RPI_HOST` (required): Raspberry hostname or IP
- `RPI_USER` (default: `pi`)
- `RPI_PORT` (default: `22`)
- `RPI_APP_DIR` (default: `~/apps/roomba-player`)
- `ROOMBA_SERIAL_PORT` (default: `/dev/ttyUSB0`)
- `ROOMBA_BAUDRATE` (default: `115200`)
- `ROOMBA_TIMEOUT_SEC` (default: `1.0`)
- `ENV_FILE` (default: `.env.rpi`)

### Deploy, install deps, restart / Déployer, installer, redémarrer

```bash
make deploy-rpi
```

This command:
1. Syncs code to Raspberry Pi
2. Creates/updates `.venv`
3. Runs `pip install -e .` on Raspberry Pi
4. Writes remote `${RPI_APP_DIR}/.env` from deployment variables
5. Restarts API process (kills previous one if running)

### Restart only / Redémarrage seul

```bash
make restart-rpi
```

### Follow logs / Suivre les logs

```bash
make logs-rpi
```

## Endpoints (v0.2)

- `GET /health` : service health check
- `GET /telemetry` : mock telemetry + serial connection status
- `WS /ws/telemetry` : telemetry event stream
- `WS /ws/control` : bidirectional control channel for Roomba OI

## WebSocket control protocol (v0.2)

Client messages are JSON objects with an `action` field.

Supported actions:
- `ping`
- `init` (connect + start + safe)
- `mode` with `value: safe|full`
- `drive` with `velocity` and `radius`
- `stop`
- `clean`
- `dock`

Example session:

```json
{"action":"init"}
{"action":"drive","velocity":120,"radius":32767}
{"action":"stop"}
```

## Safety notes / Notes de sécurité

**FR**
- Commencer toujours en mode `safe`.
- Tester roues levées avant premier mouvement.
- Prévoir un `stop` rapide en cas de comportement inattendu.

**EN**
- Start in `safe` mode first.
- Test with wheels lifted before first movement.
- Keep a quick `stop` command ready for unexpected behavior.

## Iterative roadmap / Feuille de route itérative

**FR**
1. Capteurs Roomba réels via OI (batterie, bumpers, cliff)
2. Monitoring enrichi + historiques
3. Sécurités avancées (heartbeat watchdog, e-stop)
4. Auto-pilot v1 (state machine)

**EN**
1. Real Roomba OI sensors (battery, bumpers, cliff)
2. Enriched monitoring + history
3. Advanced safety (heartbeat watchdog, e-stop)
4. Autopilot v1 (state machine)

## Contribution

**FR**: Travail en mode itératif, petites PRs, documentation mise à jour à chaque étape.

**EN**: Iterative workflow, small PRs, docs updated at each step.

## License

MIT
