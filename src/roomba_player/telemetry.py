"""Telemetry primitives (mock for initial scaffold)."""

from datetime import datetime, timezone
from random import randint


def get_telemetry_snapshot() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "battery_pct": randint(60, 100),
        "state": "idle",
        "bumper": False,
        "dock_visible": False,
    }
