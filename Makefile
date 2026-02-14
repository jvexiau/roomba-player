.PHONY: deploy-rpi restart-rpi logs-rpi

deploy-rpi:
	./scripts/deploy_rpi.sh

restart-rpi:
	RPI_SKIP_SYNC=1 RPI_SKIP_INSTALL=1 ./scripts/deploy_rpi.sh

logs-rpi:
	@test -n "$$RPI_HOST" || (echo "RPI_HOST is required" && exit 1)
	ssh -p "$${RPI_PORT:-22}" "$${RPI_USER:-pi}@$${RPI_HOST}" "tail -f $${RPI_APP_DIR:-~/apps/roomba-player}/logs/server.log"
