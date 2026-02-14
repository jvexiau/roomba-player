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
#   RPI_UPGRADE_LIBS=0
#   ROOMBA_SERIAL_PORT=/dev/ttyUSB0
#   ROOMBA_BAUDRATE=115200
#   ROOMBA_TIMEOUT_SEC=1.0
#   CAMERA_STREAM_ENABLED=false
#   CAMERA_WIDTH=800
#   CAMERA_HEIGHT=600
#   CAMERA_FRAMERATE=15
#   CAMERA_PROFILE=high
#   CAMERA_SHUTTER=12000
#   CAMERA_DENOISE=cdn_fast
#   CAMERA_SHARPNESS=1.1
#   CAMERA_AWB=auto
#   CAMERA_H264_TCP_PORT=9100
#   CAMERA_HTTP_BIND_HOST=0.0.0.0
#   CAMERA_HTTP_PORT=8081
#   CAMERA_HTTP_PATH=/stream.mjpg

ENV_FILE="${ENV_FILE:-.env.rpi}"
if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    key="${key#"${key%%[![:space:]]*}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    if [[ ( "$value" == \"*\" && "$value" == *\" ) || ( "$value" == \'*\' && "$value" == *\' ) ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$ENV_FILE"
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
RPI_UPGRADE_LIBS="${RPI_UPGRADE_LIBS:-0}"
ROOMBA_SERIAL_PORT="${ROOMBA_SERIAL_PORT:-/dev/ttyUSB0}"
ROOMBA_BAUDRATE="${ROOMBA_BAUDRATE:-115200}"
ROOMBA_TIMEOUT_SEC="${ROOMBA_TIMEOUT_SEC:-1.0}"
CAMERA_STREAM_ENABLED="${CAMERA_STREAM_ENABLED:-false}"
CAMERA_WIDTH="${CAMERA_WIDTH:-800}"
CAMERA_HEIGHT="${CAMERA_HEIGHT:-600}"
CAMERA_FRAMERATE="${CAMERA_FRAMERATE:-15}"
CAMERA_PROFILE="${CAMERA_PROFILE:-high}"
CAMERA_SHUTTER="${CAMERA_SHUTTER:-12000}"
CAMERA_DENOISE="${CAMERA_DENOISE:-cdn_fast}"
CAMERA_SHARPNESS="${CAMERA_SHARPNESS:-1.1}"
CAMERA_AWB="${CAMERA_AWB:-auto}"
CAMERA_H264_TCP_PORT="${CAMERA_H264_TCP_PORT:-9100}"
CAMERA_HTTP_BIND_HOST="${CAMERA_HTTP_BIND_HOST:-0.0.0.0}"
CAMERA_HTTP_PORT="${CAMERA_HTTP_PORT:-8081}"
CAMERA_HTTP_PATH="${CAMERA_HTTP_PATH:-/stream.mjpg}"

if [[ -z "$RPI_HOST" ]]; then
  echo "Error: RPI_HOST is required (example: raspberrypi.local or 192.168.1.42)" >&2
  exit 1
fi

SSH_TARGET="${RPI_USER}@${RPI_HOST}"
SSH_OPTS=( -p "$RPI_PORT" )
RSYNC_SSH="ssh -p ${RPI_PORT}"

echo "[1/4] Ensure app directory exists on Raspberry Pi"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s -- "$RPI_APP_DIR" <<'REMOTE_MKDIR'
set -euo pipefail
APP_DIR="$1"
if [[ "$APP_DIR" == "~/"* ]]; then
  APP_DIR="$HOME/${APP_DIR#~/}"
elif [[ "$APP_DIR" == "~" ]]; then
  APP_DIR="$HOME"
fi
mkdir -p "$APP_DIR"
REMOTE_MKDIR

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
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s -- "$RPI_APP_DIR" "$RPI_PYTHON" "$RPI_UPGRADE_LIBS" <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="$1"
PYTHON_BIN="$2"
UPGRADE_LIBS="$3"
if [[ "$APP_DIR" == "~/"* ]]; then
  APP_DIR="$HOME/${APP_DIR#~/}"
elif [[ "$APP_DIR" == "~" ]]; then
  APP_DIR="$HOME"
fi
cd "$APP_DIR"
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
if [[ "$UPGRADE_LIBS" == "1" ]]; then
  python -m pip install --upgrade pip
  pip install --upgrade setuptools wheel
  pip install --upgrade -e .
else
  pip install -e . --no-deps
fi
REMOTE_INSTALL
else
  echo "[3/4] Install skipped (RPI_SKIP_INSTALL=1)"
fi

echo "[4/4] Restart roomba-player process on Raspberry Pi"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s -- \
  "$RPI_APP_DIR" \
  "$ROOMBA_SERIAL_PORT" \
  "$ROOMBA_BAUDRATE" \
  "$ROOMBA_TIMEOUT_SEC" \
  "$CAMERA_STREAM_ENABLED" \
  "$CAMERA_WIDTH" \
  "$CAMERA_HEIGHT" \
  "$CAMERA_FRAMERATE" \
  "$CAMERA_PROFILE" \
  "$CAMERA_SHUTTER" \
  "$CAMERA_DENOISE" \
  "$CAMERA_SHARPNESS" \
  "$CAMERA_AWB" \
  "$CAMERA_H264_TCP_PORT" \
  "$CAMERA_HTTP_BIND_HOST" \
  "$CAMERA_HTTP_PORT" \
  "$CAMERA_HTTP_PATH" \
  "$RPI_BIND_HOST" \
  "$RPI_BIND_PORT" <<'REMOTE_RESTART'
set -euo pipefail
APP_DIR="$1"
ROOMBA_PORT="$2"
ROOMBA_BAUD="$3"
ROOMBA_TIMEOUT="$4"
CAMERA_ENABLED="$5"
CAMERA_WIDTH="$6"
CAMERA_HEIGHT="$7"
CAMERA_FRAMERATE="$8"
CAMERA_PROFILE="$9"
CAMERA_SHUTTER="${10}"
CAMERA_DENOISE="${11}"
CAMERA_SHARPNESS="${12}"
CAMERA_AWB="${13}"
CAMERA_H264_TCP_PORT="${14}"
CAMERA_HTTP_BIND_HOST="${15}"
CAMERA_HTTP_PORT="${16}"
CAMERA_HTTP_PATH="${17}"
BIND_HOST="${18}"
BIND_PORT="${19}"
if [[ "$APP_DIR" == "~/"* ]]; then
  APP_DIR="$HOME/${APP_DIR#~/}"
elif [[ "$APP_DIR" == "~" ]]; then
  APP_DIR="$HOME"
fi
cd "$APP_DIR"
mkdir -p logs
cat > .env <<ENVCONF
ROOMBA_PLAYER_ROOMBA_SERIAL_PORT=${ROOMBA_PORT}
ROOMBA_PLAYER_ROOMBA_BAUDRATE=${ROOMBA_BAUD}
ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC=${ROOMBA_TIMEOUT}
ROOMBA_PLAYER_CAMERA_STREAM_ENABLED=${CAMERA_ENABLED}
ROOMBA_PLAYER_CAMERA_WIDTH=${CAMERA_WIDTH}
ROOMBA_PLAYER_CAMERA_HEIGHT=${CAMERA_HEIGHT}
ROOMBA_PLAYER_CAMERA_FRAMERATE=${CAMERA_FRAMERATE}
ROOMBA_PLAYER_CAMERA_PROFILE=${CAMERA_PROFILE}
ROOMBA_PLAYER_CAMERA_SHUTTER=${CAMERA_SHUTTER}
ROOMBA_PLAYER_CAMERA_DENOISE=${CAMERA_DENOISE}
ROOMBA_PLAYER_CAMERA_SHARPNESS=${CAMERA_SHARPNESS}
ROOMBA_PLAYER_CAMERA_AWB=${CAMERA_AWB}
ROOMBA_PLAYER_CAMERA_H264_TCP_PORT=${CAMERA_H264_TCP_PORT}
ROOMBA_PLAYER_CAMERA_HTTP_BIND_HOST=${CAMERA_HTTP_BIND_HOST}
ROOMBA_PLAYER_CAMERA_HTTP_PORT=${CAMERA_HTTP_PORT}
ROOMBA_PLAYER_CAMERA_HTTP_PATH=${CAMERA_HTTP_PATH}
ENVCONF
if [ -f roomba-player.pid ]; then
  OLD_PID="$(cat roomba-player.pid || true)"
  if [ -n "${OLD_PID}" ] && kill -0 "${OLD_PID}" 2>/dev/null; then
    kill "${OLD_PID}" || true
    sleep 1
  fi
fi
pkill -f "uvicorn roomba_player.app:app" || true
. .venv/bin/activate
nohup uvicorn roomba_player.app:app --host "${BIND_HOST}" --port "${BIND_PORT}" > logs/server.log 2>&1 &
echo $! > roomba-player.pid
sleep 1
if ! kill -0 "$(cat roomba-player.pid)" 2>/dev/null; then
  echo "Process failed to start. Check logs/server.log" >&2
  exit 1
fi
REMOTE_RESTART

echo "Done. Service is up on http://${RPI_HOST}:${RPI_BIND_PORT}"
echo "Logs: ssh -p ${RPI_PORT} ${SSH_TARGET} 'tail -f ${RPI_APP_DIR}/logs/server.log'"
