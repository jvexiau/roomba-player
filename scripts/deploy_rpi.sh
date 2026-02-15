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
#   PLAN_DEFAULT_PATH=
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
#   ARUCO_ENABLED=false
#   ARUCO_INTERVAL_SEC=1.0
#   ARUCO_DICTIONARY=DICT_4X4_50
#   ARUCO_SNAP_ENABLED=true
#   ARUCO_FOCAL_PX=900.0
#   ARUCO_POSE_BLEND=0.35
#   ARUCO_THETA_BLEND=0.2
#   ARUCO_HEADING_GAIN_DEG=8.0
#   ODOMETRY_HISTORY_PATH=bdd/odometry_history.jsonl
#   ODOMETRY_SOURCE=encoders
#   ODOMETRY_MM_PER_TICK=0.445
#   ODOMETRY_LINEAR_SCALE=1.0
#   ODOMETRY_ANGULAR_SCALE=1.0
#   ODOMETRY_ROBOT_RADIUS_MM=180.0
#   ODOMETRY_COLLISION_MARGIN_SCALE=0.55

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
PLAN_DEFAULT_PATH="${PLAN_DEFAULT_PATH:-}"
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
ARUCO_ENABLED="${ARUCO_ENABLED:-false}"
ARUCO_INTERVAL_SEC="${ARUCO_INTERVAL_SEC:-1.0}"
ARUCO_DICTIONARY="${ARUCO_DICTIONARY:-DICT_4X4_50}"
ARUCO_SNAP_ENABLED="${ARUCO_SNAP_ENABLED:-true}"
ARUCO_FOCAL_PX="${ARUCO_FOCAL_PX:-900.0}"
ARUCO_POSE_BLEND="${ARUCO_POSE_BLEND:-0.35}"
ARUCO_THETA_BLEND="${ARUCO_THETA_BLEND:-0.2}"
ARUCO_HEADING_GAIN_DEG="${ARUCO_HEADING_GAIN_DEG:-8.0}"
ODOMETRY_HISTORY_PATH="${ODOMETRY_HISTORY_PATH:-bdd/odometry_history.jsonl}"
ODOMETRY_SOURCE="${ODOMETRY_SOURCE:-encoders}"
ODOMETRY_MM_PER_TICK="${ODOMETRY_MM_PER_TICK:-0.445}"
ODOMETRY_LINEAR_SCALE="${ODOMETRY_LINEAR_SCALE:-1.0}"
ODOMETRY_ANGULAR_SCALE="${ODOMETRY_ANGULAR_SCALE:-1.0}"
ODOMETRY_ROBOT_RADIUS_MM="${ODOMETRY_ROBOT_RADIUS_MM:-180.0}"
ODOMETRY_COLLISION_MARGIN_SCALE="${ODOMETRY_COLLISION_MARGIN_SCALE:-0.55}"

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
mkdir -p "$APP_DIR/plans"
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
ENV_PAYLOAD="$(cat <<EOF
ROOMBA_PLAYER_ROOMBA_SERIAL_PORT=${ROOMBA_SERIAL_PORT}
ROOMBA_PLAYER_ROOMBA_BAUDRATE=${ROOMBA_BAUDRATE}
ROOMBA_PLAYER_ROOMBA_TIMEOUT_SEC=${ROOMBA_TIMEOUT_SEC}
ROOMBA_PLAYER_PLAN_DEFAULT_PATH=${PLAN_DEFAULT_PATH}
ROOMBA_PLAYER_CAMERA_STREAM_ENABLED=${CAMERA_STREAM_ENABLED}
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
ROOMBA_PLAYER_ARUCO_ENABLED=${ARUCO_ENABLED}
ROOMBA_PLAYER_ARUCO_INTERVAL_SEC=${ARUCO_INTERVAL_SEC}
ROOMBA_PLAYER_ARUCO_DICTIONARY=${ARUCO_DICTIONARY}
ROOMBA_PLAYER_ARUCO_SNAP_ENABLED=${ARUCO_SNAP_ENABLED}
ROOMBA_PLAYER_ARUCO_FOCAL_PX=${ARUCO_FOCAL_PX}
ROOMBA_PLAYER_ARUCO_POSE_BLEND=${ARUCO_POSE_BLEND}
ROOMBA_PLAYER_ARUCO_THETA_BLEND=${ARUCO_THETA_BLEND}
ROOMBA_PLAYER_ARUCO_HEADING_GAIN_DEG=${ARUCO_HEADING_GAIN_DEG}
ROOMBA_PLAYER_ODOMETRY_HISTORY_PATH=${ODOMETRY_HISTORY_PATH}
ROOMBA_PLAYER_ODOMETRY_SOURCE=${ODOMETRY_SOURCE}
ROOMBA_PLAYER_ODOMETRY_MM_PER_TICK=${ODOMETRY_MM_PER_TICK}
ROOMBA_PLAYER_ODOMETRY_LINEAR_SCALE=${ODOMETRY_LINEAR_SCALE}
ROOMBA_PLAYER_ODOMETRY_ANGULAR_SCALE=${ODOMETRY_ANGULAR_SCALE}
ROOMBA_PLAYER_ODOMETRY_ROBOT_RADIUS_MM=${ODOMETRY_ROBOT_RADIUS_MM}
ROOMBA_PLAYER_ODOMETRY_COLLISION_MARGIN_SCALE=${ODOMETRY_COLLISION_MARGIN_SCALE}
EOF
)"
ENV_PAYLOAD_B64="$(printf '%s' "$ENV_PAYLOAD" | base64 -w0)"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s -- \
  "$RPI_APP_DIR" \
  "$RPI_BIND_HOST" \
  "$RPI_BIND_PORT" \
  "$ENV_PAYLOAD_B64" <<'REMOTE_RESTART'
set -euo pipefail
APP_DIR="${1:-$HOME/apps/roomba-player}"
BIND_HOST="${2:-0.0.0.0}"
BIND_PORT="${3:-8000}"
ENV_B64="${4:-}"
if [[ "$APP_DIR" == "~/"* ]]; then
  APP_DIR="$HOME/${APP_DIR#~/}"
elif [[ "$APP_DIR" == "~" ]]; then
  APP_DIR="$HOME"
fi
cd "$APP_DIR"
mkdir -p logs
mkdir -p plans
if [[ ! -f plans/salon.yaml && -f examples/salon.yaml ]]; then
  cp examples/salon.yaml plans/salon.yaml
fi
if [[ -n "$ENV_B64" ]]; then
  printf '%s' "$ENV_B64" | base64 -d > .env
fi
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
