"""Persistent history storage for odometry events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonlHistoryStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload: dict) -> None:
        entry = {"ts": _now_iso(), **payload}
        line = json.dumps(entry, separators=(",", ":"), ensure_ascii=True)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def clear(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("", encoding="utf-8")

    def last_pose(self) -> dict | None:
        if not self._path.exists():
            return None
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return None
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            if all(key in data for key in ("x_mm", "y_mm", "theta_deg")):
                return {
                    "x_mm": float(data["x_mm"]),
                    "y_mm": float(data["y_mm"]),
                    "theta_deg": float(data["theta_deg"]),
                }
        return None
