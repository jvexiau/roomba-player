"""Sensor-based odometry estimator."""

from __future__ import annotations

import math
from threading import Lock
from typing import Callable


HistorySink = Callable[[dict], None]
_ENCODER_MAX = 65536
_MM_PER_TICK = 0.445
_WHEEL_BASE_MM = 235.0
_EPSILON = 1e-6
_CLEARANCE_TOL_MM = 2.0


class OdometryEstimator:
    def __init__(
        self,
        history_sink: HistorySink | None = None,
        source: str = "encoders",
        mm_per_tick: float = _MM_PER_TICK,
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
        self._mm_per_tick = float(mm_per_tick)
        self._linear_scale = float(linear_scale)
        self._angular_scale = float(angular_scale)
        self._room_contour: list[tuple[float, float]] = []
        self._obstacle_polygons: list[list[tuple[float, float]]] = []
        self._robot_radius_mm = 0.0

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
            self._snap_pose_to_valid_locked()
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
                oi_delta_angle_deg = None
                if self._source == "distance_angle":
                    oi_delta_angle_deg = self._consume_oi_angle_delta_locked(telemetry)
                pose = self._update_from_encoders_locked(
                    left_counts=int(left_counts),
                    right_counts=int(right_counts),
                    bump_left=bool(telemetry.get("bump_left", False)),
                    bump_right=bool(telemetry.get("bump_right", False)),
                    oi_delta_angle_deg=oi_delta_angle_deg,
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
                expected_dx = d * math.cos(self._theta_rad)
                expected_dy = d * math.sin(self._theta_rad)
                applied_dx, applied_dy, applied_d = self._clamp_translation_locked(d, self._theta_rad)
                self._x_mm += applied_dx
                self._y_mm += applied_dy
                self._write_history_locked(
                    {
                        "event": "update",
                        "distance_mm": applied_d,
                        "angle_deg": math.degrees(dtheta),
                        "x_mm": self._x_mm,
                        "y_mm": self._y_mm,
                        "theta_deg": math.degrees(self._theta_rad),
                        "telemetry_ts": telemetry.get("timestamp"),
                        "source": "distance_angle",
                        "collision_clamped": abs(applied_dx - expected_dx) > 1e-3 or abs(applied_dy - expected_dy) > 1e-3,
                    }
                )
                self._last_delta_distance_mm = applied_d
                self._last_delta_angle_deg = math.degrees(dtheta)

            return self._snapshot_locked()

    def _update_from_encoders_locked(
        self,
        left_counts: int,
        right_counts: int,
        bump_left: bool,
        bump_right: bool,
        oi_delta_angle_deg: float | None,
        telemetry: dict,
    ) -> dict:
        dl, dr = self._consume_encoder_wheels_mm_locked(left_counts, right_counts)
        # Encoder mode is intended to be spec-accurate (Roomba 7xx reference behavior).
        d = ((dl + dr) * 0.5) * self._linear_scale
        bump_active = bump_left or bump_right
        if bump_active and d > 0.0:
            # Keep heading/rotation updates alive while preventing forward penetration.
            d = 0.0
        if oi_delta_angle_deg is not None:
            angle_deg = oi_delta_angle_deg * self._angular_scale
        else:
            angle_deg = math.degrees((dr - dl) / _WHEEL_BASE_MM) * self._angular_scale
        a = math.radians(angle_deg)
        self._theta_rad += a
        self._theta_rad = (self._theta_rad + math.pi) % (2.0 * math.pi) - math.pi
        expected_dx = d * math.cos(self._theta_rad)
        expected_dy = d * math.sin(self._theta_rad)
        applied_dx, applied_dy, applied_d = self._clamp_translation_locked(d, self._theta_rad)
        self._x_mm += applied_dx
        self._y_mm += applied_dy
        self._last_delta_distance_mm = applied_d
        self._last_delta_angle_deg = angle_deg
        if applied_d != 0.0 or a != 0.0:
            self._write_history_locked(
                {
                    "event": "update",
                    "distance_mm": applied_d,
                    "angle_deg": angle_deg,
                    "x_mm": self._x_mm,
                    "y_mm": self._y_mm,
                    "theta_deg": math.degrees(self._theta_rad),
                    "telemetry_ts": telemetry.get("timestamp"),
                    "source": "encoders",
                    "collision_clamped": abs(applied_dx - expected_dx) > 1e-3 or abs(applied_dy - expected_dy) > 1e-3,
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

        delta_left_mm = delta_left_counts * self._mm_per_tick
        delta_right_mm = delta_right_counts * self._mm_per_tick
        return delta_left_mm, delta_right_mm

    def _consume_oi_angle_delta_locked(self, telemetry: dict) -> float | None:
        if "total_angle_deg" not in telemetry:
            return None
        total = float(telemetry.get("total_angle_deg", 0) or 0.0)
        if self._last_total_angle_deg is None:
            self._last_total_angle_deg = total
            return None
        delta = total - self._last_total_angle_deg
        self._last_total_angle_deg = total
        return delta

    def get_pose(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    def apply_external_pose(
        self,
        *,
        x_mm: float,
        y_mm: float,
        theta_deg: float,
        blend_pos: float = 0.35,
        blend_theta: float = 0.2,
        source: str = "external",
    ) -> dict:
        with self._lock:
            bp = max(0.0, min(1.0, float(blend_pos)))
            bt = max(0.0, min(1.0, float(blend_theta)))
            target_x = float(x_mm)
            target_y = float(y_mm)
            target_theta = float(theta_deg)
            self._x_mm += (target_x - self._x_mm) * bp
            self._y_mm += (target_y - self._y_mm) * bp
            current_theta_deg = math.degrees(self._theta_rad)
            delta_theta_deg = ((target_theta - current_theta_deg + 180.0) % 360.0) - 180.0
            new_theta_deg = current_theta_deg + delta_theta_deg * bt
            self._theta_rad = math.radians(new_theta_deg)
            self._theta_rad = (self._theta_rad + math.pi) % (2.0 * math.pi) - math.pi
            self._snap_pose_to_valid_locked()
            self._last_delta_distance_mm = 0.0
            self._last_delta_angle_deg = 0.0
            self._write_history_locked(
                {
                    "event": "external_pose",
                    "x_mm": self._x_mm,
                    "y_mm": self._y_mm,
                    "theta_deg": math.degrees(self._theta_rad),
                    "source": source,
                    "blend_pos": bp,
                    "blend_theta": bt,
                }
            )
            return self._snapshot_locked()

    def set_collision_plan(self, plan: dict | None, robot_radius_mm: float = 180.0) -> None:
        contour: list[tuple[float, float]] = []
        obstacles: list[list[tuple[float, float]]] = []
        if isinstance(plan, dict):
            contour = self._normalize_polygon(plan.get("contour"))
            shape_map = plan.get("object_shapes") if isinstance(plan.get("object_shapes"), dict) else {}
            for obj in plan.get("objects", []) if isinstance(plan.get("objects"), list) else []:
                if not isinstance(obj, dict):
                    continue
                poly = self._object_polygon(obj=obj, shape_map=shape_map)
                if len(poly) >= 3:
                    obstacles.append(poly)
        with self._lock:
            self._room_contour = contour
            self._obstacle_polygons = obstacles
            self._robot_radius_mm = max(0.0, float(robot_radius_mm))

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

    def _snap_pose_to_valid_locked(self) -> None:
        if len(self._room_contour) < 3:
            return
        if self._is_pose_valid(self._x_mm, self._y_mm):
            return
        base_x = self._x_mm
        base_y = self._y_mm
        best: tuple[float, float, float] | None = None
        max_radius = max(300.0, self._robot_radius_mm * 3.0)
        ring_step = 20.0
        angle_step_deg = 12.0
        rings = int(max_radius / ring_step)
        for r_i in range(1, rings + 1):
            r = r_i * ring_step
            angle = 0.0
            while angle < 360.0:
                ar = math.radians(angle)
                cx = base_x + r * math.cos(ar)
                cy = base_y + r * math.sin(ar)
                if self._is_pose_valid(cx, cy):
                    dist = math.hypot(cx - base_x, cy - base_y)
                    if best is None or dist < best[2]:
                        best = (cx, cy, dist)
                        # First valid point in current ring is good enough.
                        break
                angle += angle_step_deg
            if best is not None:
                break
        if best is not None:
            self._x_mm = best[0]
            self._y_mm = best[1]

    @staticmethod
    def _normalize_polygon(raw_points) -> list[tuple[float, float]]:
        if not isinstance(raw_points, list):
            return []
        points: list[tuple[float, float]] = []
        for p in raw_points:
            if not (isinstance(p, list) and len(p) == 2):
                continue
            try:
                points.append((float(p[0]), float(p[1])))
            except Exception:
                continue
        if len(points) >= 2:
            first = points[0]
            last = points[-1]
            if abs(first[0] - last[0]) < _EPSILON and abs(first[1] - last[1]) < _EPSILON:
                points.pop()
        return points if len(points) >= 3 else []

    def _object_polygon(self, obj: dict, shape_map: dict) -> list[tuple[float, float]]:
        if isinstance(obj.get("contour"), list):
            local_poly = self._normalize_polygon(obj.get("contour"))
        else:
            shape_ref = str(obj.get("shape_ref", "")).strip()
            shape = shape_map.get(shape_ref) if isinstance(shape_map, dict) else None
            local_poly = self._normalize_polygon(shape.get("contour") if isinstance(shape, dict) else None)
        if len(local_poly) < 3:
            return []
        ox = float(obj.get("x_mm", 0.0) or 0.0)
        oy = float(obj.get("y_mm", 0.0) or 0.0)
        theta_rad = math.radians(float(obj.get("theta_deg", 0.0) or 0.0))
        c = math.cos(theta_rad)
        s = math.sin(theta_rad)
        return [(ox + (x * c - y * s), oy + (x * s + y * c)) for x, y in local_poly]

    @staticmethod
    def _point_on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> bool:
        abx = bx - ax
        aby = by - ay
        apx = px - ax
        apy = py - ay
        cross = abs(abx * apy - aby * apx)
        if cross > 1e-3:
            return False
        dot = apx * abx + apy * aby
        if dot < -_EPSILON:
            return False
        sq_len = abx * abx + aby * aby
        if dot - sq_len > _EPSILON:
            return False
        return True

    def _point_in_polygon(self, x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
        if len(polygon) < 3:
            return False
        inside = False
        n = len(polygon)
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            if self._point_on_segment(x, y, x1, y1, x2, y2):
                return True
            intersects = ((y1 > y) != (y2 > y)) and (x < ((x2 - x1) * (y - y1) / ((y2 - y1) + _EPSILON) + x1))
            if intersects:
                inside = not inside
        return inside

    @staticmethod
    def _distance_point_segment(x: float, y: float, ax: float, ay: float, bx: float, by: float) -> float:
        abx = bx - ax
        aby = by - ay
        den = abx * abx + aby * aby
        if den <= _EPSILON:
            return math.hypot(x - ax, y - ay)
        t = ((x - ax) * abx + (y - ay) * aby) / den
        t = max(0.0, min(1.0, t))
        qx = ax + t * abx
        qy = ay + t * aby
        return math.hypot(x - qx, y - qy)

    def _distance_point_to_polygon_edges(self, x: float, y: float, polygon: list[tuple[float, float]]) -> float:
        if len(polygon) < 2:
            return float("inf")
        best = float("inf")
        n = len(polygon)
        for i in range(n):
            ax, ay = polygon[i]
            bx, by = polygon[(i + 1) % n]
            best = min(best, self._distance_point_segment(x, y, ax, ay, bx, by))
        return best

    def _is_pose_valid(self, x_mm: float, y_mm: float) -> bool:
        return self._pose_clearance_mm(x_mm, y_mm) >= 0.0

    def _pose_clearance_mm(self, x_mm: float, y_mm: float) -> float:
        if len(self._room_contour) < 3:
            return float("inf")

        room_edge_dist = self._distance_point_to_polygon_edges(x_mm, y_mm, self._room_contour)
        in_room = self._point_in_polygon(x_mm, y_mm, self._room_contour)
        if not in_room:
            # Outside room => negative clearance.
            clearance = -room_edge_dist
        else:
            clearance = room_edge_dist - self._robot_radius_mm

        for poly in self._obstacle_polygons:
            obs_edge_dist = self._distance_point_to_polygon_edges(x_mm, y_mm, poly)
            in_obs = self._point_in_polygon(x_mm, y_mm, poly)
            if in_obs:
                obs_clearance = -obs_edge_dist
            else:
                obs_clearance = obs_edge_dist - self._robot_radius_mm
            clearance = min(clearance, obs_clearance)
        return clearance

    def _closest_edge_segment(
        self,
        x: float,
        y: float,
        polygon: list[tuple[float, float]],
    ) -> tuple[float, float, float, float, float] | None:
        if len(polygon) < 2:
            return None
        best: tuple[float, float, float, float, float] | None = None
        n = len(polygon)
        for i in range(n):
            ax, ay = polygon[i]
            bx, by = polygon[(i + 1) % n]
            dist = self._distance_point_segment(x, y, ax, ay, bx, by)
            if best is None or dist < best[4]:
                best = (ax, ay, bx, by, dist)
        return best

    def _nearest_collision_edge(self, x: float, y: float) -> tuple[float, float, float, float] | None:
        candidates: list[tuple[float, float, float, float, float]] = []

        room_edge = self._closest_edge_segment(x, y, self._room_contour)
        if room_edge is not None:
            in_room = self._point_in_polygon(x, y, self._room_contour)
            if (not in_room) or (room_edge[4] < self._robot_radius_mm):
                candidates.append(room_edge)

        for poly in self._obstacle_polygons:
            edge = self._closest_edge_segment(x, y, poly)
            if edge is None:
                continue
            in_obs = self._point_in_polygon(x, y, poly)
            if in_obs or (edge[4] < self._robot_radius_mm):
                candidates.append(edge)

        if not candidates:
            return None
        edge = min(candidates, key=lambda item: item[4])
        return edge[0], edge[1], edge[2], edge[3]

    @staticmethod
    def _accept_clearance(start_clearance: float, candidate_clearance: float) -> bool:
        if start_clearance >= 0.0:
            return candidate_clearance >= 0.0
        # If already in invalid/near-collision zone, allow non-degrading moves
        # (tangential sliding) and improving moves to avoid deadlocks.
        return candidate_clearance >= (start_clearance - _CLEARANCE_TOL_MM)

    def _try_slide_step_locked(
        self,
        base_x: float,
        base_y: float,
        step_dx: float,
        step_dy: float,
        probe_x: float,
        probe_y: float,
        start_clearance: float,
    ) -> tuple[float, float] | None:
        edge = self._nearest_collision_edge(probe_x, probe_y)
        if edge is None:
            edge = self._nearest_collision_edge(base_x, base_y)
        if edge is None:
            return None
        ax, ay, bx, by = edge
        ex = bx - ax
        ey = by - ay
        norm = math.hypot(ex, ey)
        if norm <= _EPSILON:
            return None
        tx = ex / norm
        ty = ey / norm
        tangent_step = step_dx * tx + step_dy * ty
        if abs(tangent_step) <= _EPSILON:
            return None

        for scale in (1.0, 0.7, 0.45, 0.25):
            move = tangent_step * scale
            cand_dx = tx * move
            cand_dy = ty * move
            cx = base_x + cand_dx
            cy = base_y + cand_dy
            clearance = self._pose_clearance_mm(cx, cy)
            if self._accept_clearance(start_clearance, clearance):
                return cand_dx, cand_dy
        return None

    def _clamp_translation_locked(self, desired_distance_mm: float, heading_rad: float) -> tuple[float, float, float]:
        if abs(desired_distance_mm) <= _EPSILON:
            return (0.0, 0.0, 0.0)
        if len(self._room_contour) < 3:
            dx = desired_distance_mm * math.cos(heading_rad)
            dy = desired_distance_mm * math.sin(heading_rad)
            return (dx, dy, desired_distance_mm)
        direction = 1.0 if desired_distance_mm >= 0.0 else -1.0
        distance = abs(desired_distance_mm)
        max_step = max(5.0, min(20.0, self._robot_radius_mm * 0.5 if self._robot_radius_mm > 0.0 else 20.0))
        step_dx_unit = direction * math.cos(heading_rad)
        step_dy_unit = direction * math.sin(heading_rad)
        remaining = distance
        cur_x = self._x_mm
        cur_y = self._y_mm
        start_clearance = self._pose_clearance_mm(cur_x, cur_y)
        moved_dx = 0.0
        moved_dy = 0.0

        while remaining > _EPSILON:
            step_len = min(max_step, remaining)
            step_dx = step_dx_unit * step_len
            step_dy = step_dy_unit * step_len
            probe_x = cur_x + step_dx
            probe_y = cur_y + step_dy
            probe_clearance = self._pose_clearance_mm(probe_x, probe_y)
            if self._accept_clearance(start_clearance, probe_clearance):
                cur_x = probe_x
                cur_y = probe_y
                moved_dx += step_dx
                moved_dy += step_dy
                start_clearance = probe_clearance
                remaining -= step_len
                continue

            slide = self._try_slide_step_locked(
                base_x=cur_x,
                base_y=cur_y,
                step_dx=step_dx,
                step_dy=step_dy,
                probe_x=probe_x,
                probe_y=probe_y,
                start_clearance=start_clearance,
            )
            if slide is None:
                break
            sdx, sdy = slide
            cur_x += sdx
            cur_y += sdy
            moved_dx += sdx
            moved_dy += sdy
            start_clearance = self._pose_clearance_mm(cur_x, cur_y)
            remaining -= step_len

        moved_norm = math.hypot(moved_dx, moved_dy)
        moved_signed = moved_norm if direction >= 0.0 else -moved_norm
        return moved_dx, moved_dy, moved_signed
