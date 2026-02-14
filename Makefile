SHELL := /usr/bin/env bash

.PHONY: deploy-rpi restart-rpi logs-rpi

deploy-rpi:
	./scripts/deploy_rpi.sh

restart-rpi:
	RPI_SKIP_SYNC=1 RPI_SKIP_INSTALL=1 ./scripts/deploy_rpi.sh

logs-rpi:
	@ENV_FILE="$${ENV_FILE:-.env.rpi}"; \
	if [[ "$$ENV_FILE" != */* ]]; then ENV_FILE="./$$ENV_FILE"; fi; \
	if [[ -f "$$ENV_FILE" ]]; then set -a; source "$$ENV_FILE"; set +a; fi; \
	test -n "$$RPI_HOST" || (echo "RPI_HOST is required (set in $$ENV_FILE or env)" && exit 1); \
	ssh -p "$${RPI_PORT:-22}" "$${RPI_USER:-pi}@$${RPI_HOST}" "tail -f $${RPI_APP_DIR:-~/apps/roomba-player}/logs/server.log"
