# Context / Handover (No Secrets)

Last update: 2026-02-15

## Scope
This file is a technical handover to resume work quickly in Codex.
It must not contain personal data, credentials, private hostnames, tokens, or local-only secrets.

## Current Product State
- Project: `roomba-player`
- Stack: FastAPI backend + browser player (HTML/CSS/JS)
- Main domains:
  - Roomba control (commands + WS)
  - Live telemetry/sensors
  - Map/plan + odometry
  - ArUco detection + overlay + pose correction
  - Camera streaming with single active viewer behavior

## Key Runtime Behavior
- Camera is expected to be ON at app startup when enabled by env/config.
- ArUco detection runs periodically even without an active viewer stream.
- Single active stream consumer policy: latest client gets stream, others must refresh to take over.
- Overlay must be aligned to the real stream size/aspect (640x480 baseline used in project).

## Important API/Routes (check before README edits)
- `POST /camera/start` exists (compat endpoint).
- Other camera/telemetry/player routes are defined in `src/roomba_player/app.py`.
- Rule: always verify code routes before documenting/deleting README endpoints.

## Code Areas To Know First
- Backend app wiring: `src/roomba_player/app.py`
- Camera lifecycle + frames: `src/roomba_player/camera.py`
- ArUco detection logic: `src/roomba_player/aruco.py`
- Odometry/collision guard: `src/roomba_player/odometry.py`
- Telemetry stream: `src/roomba_player/telemetry.py`
- Front player integration:
  - `src/roomba_player/web/static/player-camera.js`
  - `src/roomba_player/web/static/player-aruco.js`
  - `src/roomba_player/web/static/player-map.js`
  - `src/roomba_player/web/static/player-telemetry.js`

## Test Baseline
- Run all tests: `pytest -q`
- Focused suites:
  - `tests/test_odometry.py`
  - `tests/test_aruco_snap.py`
  - `tests/test_roomba_stream.py`
  - `tests/test_ws_control.py`

## Operational Commands
- Local run (example): `uvicorn roomba_player.app:app --reload`
- Stop on RPi (Make): `make stop-rpi`
- Deploy helper: `scripts/deploy_rpi.sh`
- Stop helper: `scripts/stop_rpi.sh`

## Documentation Policy
- Keep `README.md` synchronized with real behavior and route availability.
- If behavior is transitional, mark endpoints as `compat` rather than removing prematurely.
- Keep version references aligned between:
  - `README.md`
  - `pyproject.toml`
  - git tags/releases

## Open Items / Watchpoints
- Collision tuning can break tests if defaults drift from test assumptions.
- ArUco pose correction must remain deterministic and visible in realtime logs.
- Sensor stream resilience should be monitored when camera ownership changes.
- Avoid regressions where overlay stays visible after marker loss.

## Resume Checklist (for next session)
1. `git status --short`
2. `pytest -q`
3. Verify routes in `src/roomba_player/app.py`
4. Verify README endpoint list/version section
5. Only then commit/tag/push

