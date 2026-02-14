"""Sensor-based odometry estimator."""

from __future__ import annotations

import math
from threading import Lock
from typing import Callable


HistorySink = Callable[[dict], None]
_ENCODER_MAX = 65536
_MM_PER_TICK = 0.445
_WHEEL_BASE_MM = 235.0


class OdometryEstimator:
    def __init__(
        self,
        history_sink: HistorySink | None = None,
        source: str = "encoders",
        linear_scale: float = 1.0,
        angular_scale: float = 1.0,
    ) -> None:
        self._lock = Lock()
        self._x_mm = 0.0
        self._y_mm = 0.0
        self._theta_rad = 0.0
        self._last_total_distance_mm: float | None = None
        self._last_total_angle_deg: float | None = None
        self._last_left_encoder_counts: int | None = None
        self._last_right_encoder_counts: int | None = None
        self._history_sink = history_sink
        self._last_delta_distance_mm = 0.0
        self._last_delta_angle_deg = 0.0
        self._source = str(source).strip().lower() or "encoders"
        self._linear_scale = float(linear_scale)
        self._angular_scale = float(angular_scale)

    def reset(
        self,
        x_mm: float = 0.0,
        y_mm: float = 0.0,
        theta_deg: float = 0.0,
        base_total_distance_mm: float | None = None,
        base_total_angle_deg: float | None = None,
        base_left_encoder_counts: int | None = None,
        base_right_encoder_counts: int | None = None,
    ) -> None:
        with self._lock:
            self._x_mm = float(x_mm)
            self._y_mm = float(y_mm)
            self._theta_rad = math.radians(float(theta_deg))
            self._last_total_distance_mm = (
                None if base_total_distance_mm is None else float(base_total_distance_mm)
            )
            self._last_total_angle_deg = None if base_total_angle_deg is None else float(base_total_angle_deg)
            self._last_left_encoder_counts = (
                None if base_left_encoder_counts is None else int(base_left_encoder_counts) % _ENCODER_MAX
            )
            self._last_right_encoder_counts = (
                None if base_right_encoder_counts is None else int(base_right_encoder_counts) % _ENCODER_MAX
            )
            self._last_delta_distance_mm = 0.0
            self._last_delta_angle_deg = 0.0
            self._write_history_locked(
                {
                    "event": "reset",
                    "x_mm": self._x_mm,
                    "y_mm": self._y_mm,
                    "theta_deg": (math.degrees(self._theta_rad) + 360.0) % 360.0,
                }
            )

    def update_from_telemetry(self, telemetry: dict) -> dict:
        with self._lock:
            left_counts = telemetry.get("left_encoder_counts")
            right_counts = telemetry.get("right_encoder_counts")
            has_encoders = left_counts is not None and right_counts is not None
            use_encoders = self._source in ("encoders", "auto", "distance_angle")
            if use_encoders and has_encoders:
                pose = self._update_from_encoders_locked(
                    left_counts=int(left_counts),
                    right_counts=int(right_counts),
                    bump_left=bool(telemetry.get("bump_left", False)),
                    bump_right=bool(telemetry.get("bump_right", False)),
                    telemetry=telemetry,
                )
                return pose

            total_distance_mm = float(telemetry.get("total_distance_mm", 0) or 0.0)
            total_angle_deg = float(telemetry.get("total_angle_deg", 0) or 0.0)

            if self._last_total_distance_mm is None or self._last_total_angle_deg is None:
                self._last_total_distance_mm = total_distance_mm
                self._last_total_angle_deg = total_angle_deg
                return self._snapshot_locked()

            delta_distance_mm = total_distance_mm - self._last_total_distance_mm
            delta_angle_deg = total_angle_deg - self._last_total_angle_deg
            delta_distance_mm *= self._linear_scale
            delta_angle_deg *= self._angular_scale
            self._last_total_distance_mm = total_distance_mm
            self._last_total_angle_deg = total_angle_deg

            self._last_delta_distance_mm = delta_distance_mm
            self._last_delta_angle_deg = delta_angle_deg

            if delta_distance_mm != 0.0 or delta_angle_deg != 0.0:
                dtheta = math.radians(delta_angle_deg * self._angular_scale)
                self._theta_rad += dtheta
                self._theta_rad = (self._theta_rad + math.pi) % (2.0 * math.pi) - math.pi
                d = delta_distance_mm * self._linear_scale
                self._x_mm += d * math.cos(self._theta_rad)
                self._y_mm += d * math.sin(self._theta_rad)
                self._write_history_locked(
                    {
                        "event": "update",
                        "distance_mm": d,
                        "angle_deg": math.degrees(dtheta),
                        "x_mm": self._x_mm,
                        "y_mm": self._y_mm,
                        "theta_deg": math.degrees(self._theta_rad),
                        "telemetry_ts": telemetry.get("timestamp"),
                        "source": "distance_angle",
                    }
                )
                self._last_delta_distance_mm = d
                self._last_delta_angle_deg = math.degrees(dtheta)

            return self._snapshot_locked()

    def _update_from_encoders_locked(
        self,
        left_counts: int,
        right_counts: int,
        bump_left: bool,
        bump_right: bool,
        telemetry: dict,
    ) -> dict:
        if bump_left or bump_right:
            self._last_delta_distance_mm = 0.0
            self._last_delta_angle_deg = 0.0
            return self._snapshot_locked()

        dl, dr = self._consume_encoder_wheels_mm_locked(left_counts, right_counts)
        # Encoder mode is intended to be spec-accurate (Roomba 7xx reference behavior).
        # Do not apply calibration scales here.
        d = (dl + dr) * 0.5
        a = (dr - dl) / _WHEEL_BASE_MM
        self._theta_rad += a
        self._theta_rad = (self._theta_rad + math.pi) % (2.0 * math.pi) - math.pi
        self._x_mm += d * math.cos(self._theta_rad)
        self._y_mm += d * math.sin(self._theta_rad)
        self._last_delta_distance_mm = d
        self._last_delta_angle_deg = math.degrees(a)
        if d != 0.0 or a != 0.0:
            self._write_history_locked(
                {
                    "event": "update",
                    "distance_mm": d,
                    "angle_deg": math.degrees(a),
                    "x_mm": self._x_mm,
                    "y_mm": self._y_mm,
                    "theta_deg": math.degrees(self._theta_rad),
                    "telemetry_ts": telemetry.get("timestamp"),
                    "source": "encoders",
                }
            )
        return self._snapshot_locked()

    @staticmethod
    def _delta_encoder_counts(previous: int, current: int) -> int:
        delta = (current - previous + (_ENCODER_MAX // 2)) % _ENCODER_MAX - (_ENCODER_MAX // 2)
        return int(delta)

    def _consume_encoder_wheels_mm_locked(self, left_counts: int, right_counts: int) -> tuple[float, float]:
        left_counts %= _ENCODER_MAX
        right_counts %= _ENCODER_MAX
        if self._last_left_encoder_counts is None or self._last_right_encoder_counts is None:
            self._last_left_encoder_counts = left_counts
            self._last_right_encoder_counts = right_counts
            return 0.0, 0.0

        delta_left_counts = self._delta_encoder_counts(self._last_left_encoder_counts, left_counts)
        delta_right_counts = self._delta_encoder_counts(self._last_right_encoder_counts, right_counts)
        self._last_left_encoder_counts = left_counts
        self._last_right_encoder_counts = right_counts

        delta_left_mm = delta_left_counts * _MM_PER_TICK
        delta_right_mm = delta_right_counts * _MM_PER_TICK
        return delta_left_mm, delta_right_mm

    def get_pose(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict:
        return {
            "x_mm": self._x_mm,
            "y_mm": self._y_mm,
            "theta_deg": math.degrees(self._theta_rad),
            "last_delta_distance_mm": self._last_delta_distance_mm,
            "last_delta_angle_deg": self._last_delta_angle_deg,
        }

    def _write_history_locked(self, payload: dict) -> None:
        if self._history_sink is None:
            return
        try:
            self._history_sink(payload)
        except Exception:
            # History persistence must never break live control.
            return
