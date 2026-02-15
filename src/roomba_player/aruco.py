"""ArUco detection service (single-camera-source mode)."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any
from typing import Callable


class ArucoService:
    """Background ArUco detector fed with JPEG frames from the camera stream."""

    def __init__(self, *, enabled: bool, interval_sec: float, dictionary_name: str) -> None:
        self.enabled = bool(enabled)
        self.interval_sec = max(0.2, float(interval_sec))
        self.dictionary_name = str(dictionary_name or "DICT_4X4_50")
        self._lock = threading.Lock()
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._detector = None
        self._detector_error = None
        self._last_result_monotonic = 0.0
        self._result_callback: Callable[[dict[str, Any]], None] | None = None
        self._stats = {
            "frames_enqueued": 0,
            "frames_dropped": 0,
            "detect_runs": 0,
            "detect_errors": 0,
            "last_detect_duration_ms": 0.0,
            "last_detect_started_ts": None,
            "last_detect_finished_ts": None,
            "last_frame_bytes": 0,
            "last_frame_ts": None,
        }
        self._last_result: dict[str, Any] = {
            "ok": False,
            "enabled": self.enabled,
            "reason": "disabled" if not self.enabled else "idle",
            "markers": [],
            "count": 0,
            "timestamp": None,
            "frame_width": 0,
            "frame_height": 0,
        }

    def _build_detector(self):
        if self._detector is not None or self._detector_error is not None:
            return self._detector, self._detector_error
        try:
            import cv2
        except Exception:
            self._detector_error = "opencv_not_installed"
            return None, self._detector_error

        if not hasattr(cv2, "aruco"):
            self._detector_error = "opencv_aruco_missing"
            return None, self._detector_error

        dict_names = (
            "DICT_4X4_50",
            "DICT_4X4_100",
            "DICT_4X4_250",
            "DICT_4X4_1000",
            "DICT_5X5_50",
            "DICT_5X5_100",
            "DICT_5X5_250",
            "DICT_5X5_1000",
            "DICT_6X6_50",
            "DICT_6X6_100",
            "DICT_6X6_250",
            "DICT_6X6_1000",
            "DICT_7X7_50",
            "DICT_7X7_100",
            "DICT_7X7_250",
            "DICT_7X7_1000",
            "DICT_ARUCO_ORIGINAL",
            "DICT_APRILTAG_16h5",
            "DICT_APRILTAG_25h9",
            "DICT_APRILTAG_36h10",
            "DICT_APRILTAG_36h11",
        )
        dict_map = {name: getattr(cv2.aruco, name) for name in dict_names if hasattr(cv2.aruco, name)}
        if self.dictionary_name not in dict_map:
            self._detector_error = f"unsupported_dictionary:{self.dictionary_name}"
            return None, self._detector_error

        dict_id = dict_map[self.dictionary_name]
        dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
        params = cv2.aruco.DetectorParameters()
        # Tune defaults for small/far markers while keeping false positives reasonable.
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 53
        params.adaptiveThreshWinSizeStep = 4
        params.minMarkerPerimeterRate = 0.01
        params.maxMarkerPerimeterRate = 4.0
        params.minCornerDistanceRate = 0.01
        if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        if hasattr(params, "detectInvertedMarker"):
            params.detectInvertedMarker = True
        self._detector = cv2.aruco.ArucoDetector(dictionary, params)
        self._detector_error = None
        return self._detector, None

    def start(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        while True:
            try:
                self._queue.get_nowait()
            except Exception:
                break

    def enqueue_jpeg_frame(self, frame: bytes) -> None:
        if not self.enabled or not frame:
            return
        try:
            self._queue.put_nowait(frame)
            with self._lock:
                self._stats["frames_enqueued"] += 1
                self._stats["last_frame_bytes"] = len(frame)
                self._stats["last_frame_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except Exception:
                pass
            try:
                self._queue.put_nowait(frame)
                with self._lock:
                    self._stats["frames_enqueued"] += 1
                    self._stats["frames_dropped"] += 1
                    self._stats["last_frame_bytes"] = len(frame)
                    self._stats["last_frame_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            except Exception:
                pass

    def get_last_result(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._last_result)
            age_sec = time.monotonic() - self._last_result_monotonic if self._last_result_monotonic > 0 else None
            stale_after_sec = max(1.5, self.interval_sec * 2.5)
            if (
                self.enabled
                and age_sec is not None
                and age_sec > stale_after_sec
            ):
                return {
                    "ok": False,
                    "enabled": True,
                    "reason": "stale",
                    "markers": [],
                    "count": 0,
                    "timestamp": result.get("timestamp"),
                    "frame_width": int(result.get("frame_width", 0) or 0),
                    "frame_height": int(result.get("frame_height", 0) or 0),
                }
            return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "interval_sec": self.interval_sec,
                "dictionary": self.dictionary_name,
                "worker_alive": bool(self._thread and self._thread.is_alive()),
                "queue_size": self._queue.qsize(),
                "last_result": dict(self._last_result),
            }

    def set_result_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        with self._lock:
            self._result_callback = callback

    def debug(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "interval_sec": self.interval_sec,
                "dictionary": self.dictionary_name,
                "worker_alive": bool(self._thread and self._thread.is_alive()),
                "queue_size": self._queue.qsize(),
                "stats": dict(self._stats),
                "last_result": dict(self._last_result),
            }

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                frame = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._detect_frame(frame)

    def _detect_frame(self, jpeg_bytes: bytes) -> None:
        started = time.monotonic()
        with self._lock:
            self._stats["detect_runs"] += 1
            self._stats["last_detect_started_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        detector, detector_error = self._build_detector()
        if detector_error:
            with self._lock:
                self._last_result = {
                    "ok": False,
                    "enabled": True,
                    "reason": detector_error,
                    "markers": [],
                    "count": 0,
                    "timestamp": None,
                    "frame_width": 0,
                    "frame_height": 0,
                }
                self._stats["detect_errors"] += 1
                self._stats["last_detect_duration_ms"] = round((time.monotonic() - started) * 1000.0, 2)
                self._stats["last_detect_finished_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return

        try:
            import cv2
            import numpy as np

            frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                result = {
                    "ok": False,
                    "enabled": True,
                    "reason": "decode_failed",
                    "markers": [],
                    "count": 0,
                    "timestamp": None,
                    "frame_width": 0,
                    "frame_height": 0,
                }
            else:
                frame_height, frame_width = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                attempts: list[tuple[Any, float]] = [(gray, 1.0)]
                if min(frame_width, frame_height) <= 1000:
                    upscaled = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                    # `scale_back` converts upscaled coordinates back to original frame pixels.
                    attempts.append((upscaled, 0.5))
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                attempts.append((clahe.apply(gray), 1.0))

                corners = None
                ids = None
                for attempt_img, scale_back in attempts:
                    detected_corners, detected_ids, _rej = detector.detectMarkers(attempt_img)
                    if detected_ids is None or len(detected_ids) == 0:
                        continue
                    corners = detected_corners
                    ids = detected_ids
                    if scale_back != 1.0:
                        corners = [c.astype("float32") * scale_back for c in corners]
                    break

                markers = []
                if ids is not None and len(ids) > 0:
                    for i, marker_id in enumerate(ids.flatten().tolist()):
                        pts = corners[i].reshape((4, 2))
                        center_x = float(pts[:, 0].mean())
                        center_y = float(pts[:, 1].mean())
                        markers.append(
                            {
                                "id": int(marker_id),
                                "corners": [[float(p[0]), float(p[1])] for p in pts.tolist()],
                                "center": [center_x, center_y],
                                "area_px": float(cv2.contourArea(pts.astype("float32"))),
                            }
                        )
                result = {
                    "ok": True,
                    "enabled": True,
                    "reason": "detected",
                    "markers": markers,
                    "count": len(markers),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "frame_width": int(frame_width),
                    "frame_height": int(frame_height),
                }
        except Exception as exc:
            result = {
                "ok": False,
                "enabled": True,
                "reason": f"detect_error:{exc}",
                "markers": [],
                "count": 0,
                "timestamp": None,
                "frame_width": 0,
                "frame_height": 0,
            }
            with self._lock:
                self._stats["detect_errors"] += 1

        with self._lock:
            self._last_result = result
            self._last_result_monotonic = time.monotonic()
            self._stats["last_detect_duration_ms"] = round((time.monotonic() - started) * 1000.0, 2)
            self._stats["last_detect_finished_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            callback = self._result_callback
        if callback is not None:
            try:
                callback(dict(result))
            except Exception:
                pass
