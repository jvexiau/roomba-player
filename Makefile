SHELL := /usr/bin/env bash

.PHONY: deploy-rpi update-rpi restart-rpi stop logs-rpi

deploy-rpi:
	./scripts/deploy_rpi.sh

update-rpi:
	RPI_UPGRADE_LIBS=1 ./scripts/deploy_rpi.sh

restart-rpi:
	RPI_SKIP_SYNC=1 RPI_SKIP_INSTALL=1 ./scripts/deploy_rpi.sh

stop:
	@ENV_FILE="$${ENV_FILE:-.env.rpi}"; \
	if [[ "$$ENV_FILE" != */* ]]; then ENV_FILE="./$$ENV_FILE"; fi; \
	if [[ -f "$$ENV_FILE" ]]; then set -a; source "$$ENV_FILE"; set +a; fi; \
	test -n "$$RPI_HOST" || (echo "RPI_HOST is required (set in $$ENV_FILE or env)" && exit 1); \
	ssh -p "$${RPI_PORT:-22}" "$${RPI_USER:-pi}@$${RPI_HOST}" bash -s -- "$${RPI_APP_DIR:-~/apps/roomba-player}" <<'REMOTE_STOP' \
set -euo pipefail; \
APP_DIR="$$1"; \
if [[ "$$APP_DIR" == "~/"* ]]; then APP_DIR="$$HOME/$${APP_DIR#~/}"; elif [[ "$$APP_DIR" == "~" ]]; then APP_DIR="$$HOME"; fi; \
cd "$$APP_DIR"; \
if [ -f roomba-player.pid ]; then \
  PID="$$(cat roomba-player.pid || true)"; \
  if [ -n "$$PID" ] && kill -0 "$$PID" 2>/dev/null; then kill "$$PID" || true; sleep 1; fi; \
fi; \
pkill -f "uvicorn roomba_player.app:app" || true; \
echo "roomba-player stopped"; \
REMOTE_STOP

logs-rpi:
	@ENV_FILE="$${ENV_FILE:-.env.rpi}"; \
	if [[ "$$ENV_FILE" != */* ]]; then ENV_FILE="./$$ENV_FILE"; fi; \
	if [[ -f "$$ENV_FILE" ]]; then set -a; source "$$ENV_FILE"; set +a; fi; \
	test -n "$$RPI_HOST" || (echo "RPI_HOST is required (set in $$ENV_FILE or env)" && exit 1); \
	ssh -p "$${RPI_PORT:-22}" "$${RPI_USER:-pi}@$${RPI_HOST}" "tail -f $${RPI_APP_DIR:-~/apps/roomba-player}/logs/server.log"
