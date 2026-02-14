"""Roomba Open Interface adapter over USB serial."""

from __future__ import annotations

import threading

try:
    import serial
except ImportError:  # pragma: no cover - handled at runtime when command is sent
    serial = None


_CMD_START = 128
_CMD_SAFE = 131
_CMD_FULL = 132
_CMD_CLEAN = 135
_CMD_DRIVE = 137
_CMD_DOCK = 143


def _int16_bytes(value: int) -> bytes:
    if value < 0:
        value = (1 << 16) + value
    return bytes(((value >> 8) & 0xFF, value & 0xFF))


class RoombaOI:
    """Minimal Roomba Open Interface controller."""

    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def connect(self) -> None:
        if self.connected:
            return
        if serial is None:
            raise RuntimeError("Missing dependency: pyserial. Install with `pip install pyserial`.")
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def close(self) -> None:
        if self.connected:
            self._serial.close()
        self._serial = None

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
        radius = max(-2000, min(2000, int(radius)))
        command = bytes([_CMD_DRIVE]) + _int16_bytes(velocity) + _int16_bytes(radius)
        self.write(command)

    def stop(self) -> None:
        self.drive(0, 0)
