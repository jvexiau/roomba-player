#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   RPI_HOST=raspberrypi.local RPI_USER=pi ./scripts/deploy_rpi.sh
#
# Optional env vars:
#   ENV_FILE=.env.rpi
#   RPI_PORT=22
#   RPI_APP_DIR=~/apps/roomba-player
#   RPI_PYTHON=python3
#   RPI_BIND_HOST=0.0.0.0
#   RPI_BIND_PORT=8000
#   RPI_SKIP_SYNC=0
#   RPI_SKIP_INSTALL=0
#   ROOMBA_SERIAL_PORT=/dev/ttyUSB0
#   ROOMBA_BAUDRATE=115200
#   ROOMBA_TIMEOUT_SEC=1.0

ENV_FILE="${ENV_FILE:-.env.rpi}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

RPI_HOST="${RPI_HOST:-}"
RPI_USER="${RPI_USER:-pi}"
RPI_PORT="${RPI_PORT:-22}"
RPI_APP_DIR="${RPI_APP_DIR:-~/apps/roomba-player}"
RPI_PYTHON="${RPI_PYTHON:-python3}"
RPI_BIND_HOST="${RPI_BIND_HOST:-0.0.0.0}"
RPI_BIND_PORT="${RPI_BIND_PORT:-8000}"
RPI_SKIP_SYNC="${RPI_SKIP_SYNC:-0}"
RPI_SKIP_INSTALL="${RPI_SKIP_INSTALL:-0}"
ROOMBA_SERIAL_PORT="${ROOMBA_SERIAL_PORT:-/dev/ttyUSB0}"
ROOMBA_BAUDRATE="${ROOMBA_BAUDRATE:-115200}"
ROOMBA_TIMEOUT_SEC="${ROOMBA_TIMEOUT_SEC:-1.0}"

if [[ -z "$RPI_HOST" ]]; then
  echo "Error: RPI_HOST is required (example: raspberrypi.local or 192.168.1.42)" >&2
  exit 1
fi

SSH_TARGET="${RPI_USER}@${RPI_HOST}"
SSH_OPTS=( -p "$RPI_PORT" )
RSYNC_SSH="ssh -p ${RPI_PORT}"

echo "[1/4] Ensure app directory exists on Raspberry Pi"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p ${RPI_APP_DIR}"

if [[ "$RPI_SKIP_SYNC" != "1" ]]; then
  echo "[2/4] Sync code to Raspberry Pi"
  rsync -az --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.env' \
    --exclude '.env.*' \
    -e "$RSYNC_SSH" \
    ./ "$SSH_TARGET:$RPI_APP_DIR/"
else
  echo "[2/4] Sync skipped (RPI_SKIP_SYNC=1)"
fi

if [[ "$RPI_SKIP_INSTALL" != "1" ]]; then
  echo "[3/4] Install/update Python dependencies on Raspberry Pi"
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "bash -lc '
    set -euo pipefail
    cd ${RPI_APP_DIR}
    ${RPI_PYTHON} -m venv .venv
    . .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -e .
  '"
else
  echo "[3/4] Install skipped (RPI_SKIP_INSTALL=1)"
fi

echo "[4/4] Restart roomba-player process on Raspberry Pi"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "bash -lc '
  set -euo pipefail
  cd ${RPI_APP_DIR}
  mkdir -p logs
  cat > .env <<EOF
ROOMBA_PLAYER_ROOMBA_SERIAL_PORT=${ROOMBA_SERIAL_PORT}
ROOMBA_PLAYER_ROOMBA_BAUDRATE=${ROOMBA_BAUDRATE}
ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC=${ROOMBA_TIMEOUT_SEC}
EOF
  if [ -f roomba-player.pid ]; then
    OLD_PID=\$(cat roomba-player.pid || true)
    if [ -n \"\${OLD_PID}\" ] && kill -0 \"\${OLD_PID}\" 2>/dev/null; then
      kill \"\${OLD_PID}\" || true
      sleep 1
    fi
  fi
  pkill -f \"uvicorn roomba_player.app:app\" || true
  . .venv/bin/activate
  nohup uvicorn roomba_player.app:app --host ${RPI_BIND_HOST} --port ${RPI_BIND_PORT} > logs/server.log 2>&1 &
  echo \$! > roomba-player.pid
  sleep 1
  if ! kill -0 \$(cat roomba-player.pid) 2>/dev/null; then
    echo \"Process failed to start. Check logs/server.log\" >&2
    exit 1
  fi
'"

echo "Done. Service is up on http://${RPI_HOST}:${RPI_BIND_PORT}"
echo "Logs: ssh -p ${RPI_PORT} ${SSH_TARGET} 'tail -f ${RPI_APP_DIR}/logs/server.log'"
