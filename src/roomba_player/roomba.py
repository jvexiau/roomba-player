"""Roomba Open Interface adapter over USB serial."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import serial
except ImportError:  # pragma: no cover - handled at runtime when command is sent
    serial = None


_CMD_START = 128
_CMD_SAFE = 131
_CMD_FULL = 132
_CMD_CLEAN = 135
_CMD_DRIVE = 137
_CMD_STREAM = 148
_CMD_PAUSE_RESUME_STREAM = 150
_CMD_DOCK = 143

_RADIUS_STRAIGHT = 32768
_RADIUS_INPLACE_CW = -1
_RADIUS_INPLACE_CCW = 1

_STREAM_HEADER = 19
_STREAM_PACKETS_DEFAULT = (7, 8, 9, 10, 11, 12, 19, 20, 21, 25, 26, 34, 43, 44)

_PACKET_SIZE = {
    7: 1,   # bumps and wheel drops
    8: 1,   # wall
    9: 1,   # cliff left
    10: 1,  # cliff front left
    11: 1,  # cliff front right
    12: 1,  # cliff right
    19: 2,  # distance (mm, signed)
    20: 2,  # angle (deg, signed)
    21: 1,  # charging state
    25: 2,  # battery charge (mAh)
    26: 2,  # battery capacity (mAh)
    34: 1,  # charging sources available (home base bit)
    43: 2,  # left encoder counts (unsigned)
    44: 2,  # right encoder counts (unsigned)
}

_CHARGING_STATE = {
    0: "not_charging",
    1: "reconditioning",
    2: "full_charging",
    3: "trickle_charging",
    4: "waiting",
    5: "charging_fault",
}


def _int16_bytes(value: int) -> bytes:
    if value < 0:
        value = (1 << 16) + value
    return bytes(((value >> 8) & 0xFF, value & 0xFF))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RoombaOI:
    """Roomba Open Interface controller with sensor stream support."""

    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self._lock = threading.Lock()

        self._stream_stop = threading.Event()
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_buffer = bytearray()
        self._stream_packet_ids: tuple[int, ...] = _STREAM_PACKETS_DEFAULT
        self._last_stream_update_monotonic = 0.0
        self._last_stream_start_monotonic = 0.0

        self._telemetry_lock = threading.Lock()
        self._telemetry = {
            "timestamp": _now_iso(),
            "battery_pct": 0,
            "state": "disconnected",
            "bumper": False,
            "bump_left": False,
            "bump_right": False,
            "wheel_drop_left": False,
            "wheel_drop_right": False,
            "wheel_drop_caster": False,
            "wall_seen": False,
            "cliff_left": False,
            "cliff_front_left": False,
            "cliff_front_right": False,
            "cliff_right": False,
            "dock_visible": False,
            "charging_source_home_base": False,
            "charging_source_internal": False,
            "roomba_connected": False,
            "battery_charge_mah": 0,
            "battery_capacity_mah": 0,
            "charging_state_code": 0,
            "distance_mm": 0,
            "angle_deg": 0,
            "total_distance_mm": 0,
            "total_angle_deg": 0,
            "left_encoder_counts": 0,
            "right_encoder_counts": 0,
        }

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def get_telemetry_snapshot(self) -> dict:
        with self._telemetry_lock:
            payload = dict(self._telemetry)
        payload["roomba_connected"] = self.connected
        return payload

    def connect(self) -> None:
        if self.connected:
            return
        if serial is None:
            raise RuntimeError("Missing dependency: pyserial. Install with `pip install pyserial`.")
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        with self._telemetry_lock:
            self._telemetry["roomba_connected"] = True
            self._telemetry["timestamp"] = _now_iso()

    def close(self) -> None:
        self.stop_sensor_stream()
        if self.connected:
            self._serial.close()
        self._serial = None
        with self._telemetry_lock:
            self._telemetry["roomba_connected"] = False
            self._telemetry["state"] = "disconnected"
            self._telemetry["timestamp"] = _now_iso()

    def write(self, payload: bytes) -> None:
        with self._lock:
            if not self.connected:
                self.connect()
            self._serial.write(payload)
            self._serial.flush()

    def start(self) -> None:
        self.write(bytes([_CMD_START]))

    def safe(self) -> None:
        self.write(bytes([_CMD_SAFE]))

    def full(self) -> None:
        self.write(bytes([_CMD_FULL]))

    def clean(self) -> None:
        self.write(bytes([_CMD_CLEAN]))

    def dock(self) -> None:
        self.write(bytes([_CMD_DOCK]))

    def drive(self, velocity: int, radius: int) -> None:
        velocity = max(-500, min(500, int(velocity)))
        radius = int(radius)
        if radius not in (_RADIUS_STRAIGHT, _RADIUS_INPLACE_CW, _RADIUS_INPLACE_CCW):
            radius = max(-2000, min(2000, radius))
        command = bytes([_CMD_DRIVE]) + _int16_bytes(velocity) + _int16_bytes(radius)
        self.write(command)

    def stop(self) -> None:
        self.drive(0, 0)

    def start_sensor_stream(self, packet_ids: tuple[int, ...] = _STREAM_PACKETS_DEFAULT) -> None:
        if not packet_ids:
            raise ValueError("At least one sensor packet id is required.")
        self._stream_packet_ids = tuple(packet_ids)
        self.write(bytes([_CMD_STREAM, len(packet_ids), *packet_ids]))
        self._last_stream_start_monotonic = time.monotonic()
        self._start_stream_reader()

    def stop_sensor_stream(self) -> None:
        self._stream_stop.set()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=1.0)
        self._stream_thread = None
        self._stream_buffer.clear()
        if self.connected:
            try:
                self.write(bytes([_CMD_PAUSE_RESUME_STREAM, 0]))
            except Exception:
                pass

    def _start_stream_reader(self) -> None:
        if self._stream_thread and self._stream_thread.is_alive():
            return
        self._stream_stop.clear()
        self._stream_thread = threading.Thread(target=self._stream_reader_loop, daemon=True)
        self._stream_thread.start()

    def _stream_reader_loop(self) -> None:
        while not self._stream_stop.is_set() and self.connected:
            try:
                chunk = self._serial.read(self._serial.in_waiting or 1)
            except Exception:
                break
            if not chunk:
                continue
            self._stream_buffer.extend(chunk)
            self._consume_stream_buffer()

    def _consume_stream_buffer(self) -> None:
        while len(self._stream_buffer) >= 3:
            if self._stream_buffer[0] != _STREAM_HEADER:
                del self._stream_buffer[0]
                continue
            payload_len = self._stream_buffer[1]
            frame_len = payload_len + 3
            if len(self._stream_buffer) < frame_len:
                return
            frame = bytes(self._stream_buffer[:frame_len])
            del self._stream_buffer[:frame_len]
            if (sum(frame) & 0xFF) != 0:
                continue
            payload = frame[2:-1]
            self._apply_stream_payload(payload)

    def _apply_stream_payload(self, payload: bytes) -> None:
        i = 0
        while i < len(payload):
            packet_id = payload[i]
            i += 1
            size = _PACKET_SIZE.get(packet_id)
            if size is None or i + size > len(payload):
                return
            data = payload[i : i + size]
            i += size
            self._apply_sensor_packet(packet_id, data)
        with self._telemetry_lock:
            self._telemetry["timestamp"] = _now_iso()
        self._last_stream_update_monotonic = time.monotonic()

    def ensure_sensor_stream(self, max_stale_sec: float = 3.0, restart_cooldown_sec: float = 2.0) -> None:
        """Best-effort stream watchdog.

        Restarts stream if reader thread is down or no packet has been received for too long.
        """
        if not self.connected:
            return
        now = time.monotonic()
        thread_alive = bool(self._stream_thread and self._stream_thread.is_alive())
        stale = self._last_stream_update_monotonic > 0 and (now - self._last_stream_update_monotonic) > max_stale_sec
        no_data_yet = self._last_stream_update_monotonic == 0 and (now - self._last_stream_start_monotonic) > max_stale_sec
        should_restart = (not thread_alive) or stale or no_data_yet
        if not should_restart:
            return
        if self._last_stream_start_monotonic and (now - self._last_stream_start_monotonic) < restart_cooldown_sec:
            return
        self.start_sensor_stream(self._stream_packet_ids)

    def _apply_sensor_packet(self, packet_id: int, data: bytes) -> None:
        with self._telemetry_lock:
            if packet_id == 7:
                bits = data[0]
                # packet 7 bit mapping
                bump_right = bool(bits & (1 << 0))
                bump_left = bool(bits & (1 << 1))
                wheel_drop_right = bool(bits & (1 << 2))
                wheel_drop_left = bool(bits & (1 << 3))
                wheel_drop_caster = bool(bits & (1 << 4))
                self._telemetry["bump_left"] = bump_left
                self._telemetry["bump_right"] = bump_right
                self._telemetry["wheel_drop_left"] = wheel_drop_left
                self._telemetry["wheel_drop_right"] = wheel_drop_right
                self._telemetry["wheel_drop_caster"] = wheel_drop_caster
                self._telemetry["bumper"] = bump_left or bump_right
            elif packet_id == 8:
                self._telemetry["wall_seen"] = bool(data[0])
            elif packet_id == 9:
                self._telemetry["cliff_left"] = bool(data[0])
            elif packet_id == 10:
                self._telemetry["cliff_front_left"] = bool(data[0])
            elif packet_id == 11:
                self._telemetry["cliff_front_right"] = bool(data[0])
            elif packet_id == 12:
                self._telemetry["cliff_right"] = bool(data[0])
            elif packet_id == 19:
                distance_mm = int.from_bytes(data, "big", signed=True)
                self._telemetry["distance_mm"] = distance_mm
                self._telemetry["total_distance_mm"] = int(self._telemetry.get("total_distance_mm", 0)) + distance_mm
            elif packet_id == 20:
                angle_deg = int.from_bytes(data, "big", signed=True)
                self._telemetry["angle_deg"] = angle_deg
                self._telemetry["total_angle_deg"] = int(self._telemetry.get("total_angle_deg", 0)) + angle_deg
            elif packet_id == 21:
                code = int(data[0])
                self._telemetry["charging_state_code"] = code
                self._telemetry["state"] = _CHARGING_STATE.get(code, f"unknown_{code}")
            elif packet_id == 25:
                self._telemetry["battery_charge_mah"] = int.from_bytes(data, "big", signed=False)
            elif packet_id == 26:
                self._telemetry["battery_capacity_mah"] = int.from_bytes(data, "big", signed=False)
            elif packet_id == 34:
                bits = data[0]
                # packet 34: bit0 internal charger, bit1 home base
                self._telemetry["charging_source_internal"] = bool(bits & 0x01)
                self._telemetry["charging_source_home_base"] = bool(bits & 0x02)
                self._telemetry["dock_visible"] = bool(bits & 0x02)
            elif packet_id == 43:
                self._telemetry["left_encoder_counts"] = int.from_bytes(data, "big", signed=False)
            elif packet_id == 44:
                self._telemetry["right_encoder_counts"] = int.from_bytes(data, "big", signed=False)

            capacity = int(self._telemetry.get("battery_capacity_mah", 0) or 0)
            charge = int(self._telemetry.get("battery_charge_mah", 0) or 0)
            if capacity > 0:
                self._telemetry["battery_pct"] = max(0, min(100, int((charge * 100) / capacity)))
