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

**FR**: v0.2 initialisée: streaming télémétrie + pilotage Roomba via WebSocket sur connecteur USB-serial (Roomba OI).

**EN**: v0.2 initialized: telemetry streaming + Roomba control over WebSocket with USB-serial connector (Roomba OI).

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
├── docs/architecture.md
├── src/roomba_player/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── roomba.py
│   ├── telemetry.py
│   └── ws.py
├── tests/test_health.py
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

### 2) Configure serial device / Configurer le port série

```bash
export ROOMBA_PLAYER_ROOMBA_SERIAL_PORT=/dev/ttyUSB0
export ROOMBA_PLAYER_ROOMBA_BAUDRATE=115200
```

### 3) Run API / Lancer l'API

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

### 4) Smoke check / Vérification

```bash
curl http://localhost:8000/health
```

Expected response / Réponse attendue:

```json
{"status":"ok","service":"roomba-player"}
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
