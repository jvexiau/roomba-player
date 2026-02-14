"""Plan loading and storage."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

import yaml


class PlanManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._plan: dict[str, Any] | None = None

    def load_from_file(self, path: str) -> dict[str, Any]:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        ext = p.suffix.lower()
        if ext in (".yaml", ".yml"):
            payload = yaml.safe_load(text)
        elif ext == ".json":
            payload = json.loads(text)
        else:
            # Fallback: try JSON first then YAML.
            try:
                payload = json.loads(text)
            except Exception:
                payload = yaml.safe_load(text)
        return self.load_from_json(payload)

    def load_from_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate(payload)
        with self._lock:
            self._plan = payload
        return payload

    def get(self) -> dict[str, Any] | None:
        with self._lock:
            if self._plan is None:
                return None
            return dict(self._plan)

    @staticmethod
    def _validate(payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ValueError("Plan must be a JSON object.")
        contour = payload.get("contour")
        if not isinstance(contour, list) or len(contour) < 3:
            raise ValueError("Plan must contain `contour` with at least 3 points.")
        for p in contour:
            if not (isinstance(p, list) and len(p) == 2):
                raise ValueError("Each contour point must be [x, y].")
