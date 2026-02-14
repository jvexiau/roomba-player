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

**FR**: Initialisation du socle projet (MVP architecture + outillage).

**EN**: Project scaffold initialized (MVP architecture + tooling).

## Tech stack (initial)

- Python 3.11+
- FastAPI (HTTP + WebSocket)
- Uvicorn
- Pydantic
- Pytest

## Repository layout / Structure

```text
.
├── .github/workflows/ci.yml
├── docs/architecture.md
├── src/roomba_player/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
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

### 2) Run API / Lancer l'API

```bash
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

### 3) Smoke check / Vérification

```bash
curl http://localhost:8000/health
```

Expected response / Réponse attendue:

```json
{"status":"ok","service":"roomba-player"}
```

## Endpoints (initial)

- `GET /health` : service health check
- `GET /telemetry` : mock telemetry snapshot
- `WS /ws/telemetry` : telemetry event stream

## Iterative roadmap / Feuille de route itérative

**FR**
1. Connecteur Roomba réel (Bluetooth/Serial selon modèle)
2. WebSocket bidirectionnel pour commandes manuelles
3. Monitoring enrichi (batterie, erreurs, capteurs)
4. Journalisation structurée + métriques
5. Auto-pilot v1 (state machine simple + garde-fous)

**EN**
1. Real Roomba connector (Bluetooth/Serial depending on model)
2. Bidirectional WebSocket for manual commands
3. Enriched monitoring (battery, faults, sensors)
4. Structured logging + metrics
5. Autopilot v1 (simple state machine + safeguards)

## Contribution

**FR**: Travail en mode itératif, petites PRs, documentation mise à jour à chaque étape.

**EN**: Iterative workflow, small PRs, docs updated at each step.

## License

MIT (you can adjust this later / modifiable ensuite)
