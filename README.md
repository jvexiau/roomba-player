# roomba-player

> **FR**: Plateforme Python pour piloter, visualiser, monitorer et auto-piloter un Roomba via Raspberry Pi.
>
> **EN**: Python platform to control, visualize, monitor, and auto-drive a Roomba through a Raspberry Pi.

## Project provenance / Provenance du code

**FR**: Ce programme est développé uniquement avec Codex, sans intervention humaine directe dans l'écriture du code.

**EN**: This program is developed only with Codex, with no direct human intervention in code writing.

## Requirements / Prérequis

### Python modules

Installed by project install:
- `fastapi`
- `uvicorn`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
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

### Hardware

- Raspberry Pi connected to Roomba through USB serial adapter (OI pin)
- Typical serial device: `/dev/ttyUSB0` or `/dev/ttyACM0`

## Local run (optional) / Lancement local (optionnel)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn roomba_player.app:app --reload --host 0.0.0.0 --port 8000
```

## Deploy to Raspberry Pi (from PC) / Déployer sur Raspberry Pi (depuis le PC)

Run all `make` commands from the repository root on your PC.

### Step 1: Prepare deploy config / Préparer la config de déploiement

```bash
cp .env.rpi.example .env.rpi
```

Edit `.env.rpi` and set at least:
- `RPI_HOST`
- `RPI_USER`
- `RPI_PORT` (if not 22)
- `RPI_APP_DIR`
- `ROOMBA_SERIAL_PORT`
- `ROOMBA_BAUDRATE`
- `ROOMBA_TIMEOUT_SEC`

Notes:
- `.env.rpi` is a local file on your PC (not committed to Git).
- You can use another file with `ENV_FILE=/path/to/file make deploy-rpi`.

### Step 2: Deploy + install dependencies + restart / Déployer + installer + redémarrer

```bash
make deploy-rpi
```

What this does:
1. Syncs code to Raspberry Pi
2. Creates/updates remote virtualenv
3. Installs Python dependencies (`pip install -e .`)
4. Writes remote `.env`
5. Stops previous process if running and starts `uvicorn`

### Optional: Force update pip libraries / Optionnel: forcer la mise à jour des libs pip

```bash
make update-rpi
```

This command does the same deployment flow, but forces:
- `pip install --upgrade setuptools wheel`
- `pip install --upgrade -e .`

Default `make deploy-rpi` does not upgrade pip libraries.

### Step 3: Follow logs / Suivre les logs

```bash
make logs-rpi
```

### Step 4: Restart only / Redémarrage seul

```bash
make restart-rpi
```

## API endpoints

- `GET /health`
- `GET /telemetry`
- `WS /ws/telemetry`
- `WS /ws/control`

## WebSocket control protocol

Client message format:

```json
{"action":"init"}
```

Supported actions:
- `ping`
- `init`
- `mode` with `value: safe|full`
- `drive` with `velocity` and `radius`
- `stop`
- `clean`
- `dock`

Example:

```json
{"action":"init"}
{"action":"drive","velocity":120,"radius":32767}
{"action":"stop"}
```

## Safety notes / Notes de sécurité

- Start with wheels lifted for first movement tests.
- Use `safe` mode first.
- Keep `stop` readily available.

## License

MIT
