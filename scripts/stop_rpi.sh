#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ENV_FILE=.env.rpi ./scripts/stop_rpi.sh
# or
#   RPI_HOST=raspberrypi.local RPI_USER=pi RPI_PORT=22 ./scripts/stop_rpi.sh

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

if [[ -z "$RPI_HOST" ]]; then
  echo "RPI_HOST is required (set in ${ENV_FILE} or env)" >&2
  exit 1
fi

SSH_TARGET="${RPI_USER}@${RPI_HOST}"
SSH_OPTS=(-p "$RPI_PORT")

echo "Stopping roomba-player on ${SSH_TARGET}:${RPI_APP_DIR}"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s -- "$RPI_APP_DIR" <<'REMOTE_STOP'
set -euo pipefail
APP_DIR="$1"
if [[ "$APP_DIR" == "~/"* ]]; then
  APP_DIR="$HOME/${APP_DIR#~/}"
elif [[ "$APP_DIR" == "~" ]]; then
  APP_DIR="$HOME"
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "App directory not found: $APP_DIR"
  exit 0
fi
cd "$APP_DIR"

if [[ -f roomba-player.pid ]]; then
  PID="$(cat roomba-player.pid || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true
    sleep 1
    if kill -0 "${PID}" 2>/dev/null; then
      kill -9 "${PID}" 2>/dev/null || true
    fi
  fi
  rm -f roomba-player.pid
fi

pkill -f "uvicorn roomba_player.app:app" 2>/dev/null || true
pkill -f "python.*-m uvicorn.*roomba_player.app:app" 2>/dev/null || true

echo "roomba-player stopped"
REMOTE_STOP
