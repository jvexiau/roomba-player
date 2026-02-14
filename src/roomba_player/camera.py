"""Raspberry camera streaming pipeline (rpicam-vid -> ffmpeg -> HTTP MJPEG)."""

from __future__ import annotations

import subprocess
import threading
import time


class CameraService:
    """Best-effort camera pipeline launcher.

    Pipeline:
    - `rpicam-vid` outputs H264 over local TCP
    - `ffmpeg` listens on this TCP stream and serves MJPEG over local HTTP
    """

    def __init__(
        self,
        *,
        enabled: bool,
        width: int,
        height: int,
        framerate: int,
        profile: str,
        shutter: int,
        denoise: str,
        sharpness: float,
        awb: str,
        h264_tcp_port: int,
        http_bind_host: str,
        http_port: int,
        http_path: str,
    ) -> None:
        self.enabled = enabled
        self.width = width
        self.height = height
        self.framerate = framerate
        self.profile = profile
        self.shutter = shutter
        self.denoise = denoise
        self.sharpness = sharpness
        self.awb = awb
        self.h264_tcp_port = h264_tcp_port
        self.http_bind_host = http_bind_host
        self.http_port = http_port
        self.http_path = http_path if http_path.startswith("/") else f"/{http_path}"

        self._lock = threading.RLock()
        self._camera_process = None
        self._ffmpeg_process = None

    @property
    def stream_url(self) -> str:
        return f"http://{self.http_bind_host}:{self.http_port}{self.http_path}"

    def start_if_enabled(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "started": False, "reason": "disabled", "stream_url": ""}

        with self._lock:
            ffmpeg_running = self._is_running(self._ffmpeg_process)
            camera_running = self._is_running(self._camera_process)
            if ffmpeg_running and camera_running:
                return {
                    "enabled": True,
                    "started": False,
                    "reason": "already_running",
                    "stream_url": self.stream_url,
                }

            self._terminate(self._camera_process)
            self._terminate(self._ffmpeg_process)
            self._camera_process = None
            self._ffmpeg_process = None

            try:
                self._start_ffmpeg()
                time.sleep(0.25)
                self._start_camera()
            except Exception as exc:
                self._terminate(self._camera_process)
                self._terminate(self._ffmpeg_process)
                self._camera_process = None
                self._ffmpeg_process = None
                return {
                    "enabled": True,
                    "started": False,
                    "reason": f"start_failed:{type(exc).__name__}",
                    "stream_url": self.stream_url,
                }

            return {
                "enabled": True,
                "started": True,
                "reason": "started",
                "stream_url": self.stream_url,
            }

    def stop(self) -> None:
        with self._lock:
            self._terminate(self._camera_process)
            self._terminate(self._ffmpeg_process)
            self._camera_process = None
            self._ffmpeg_process = None

    @staticmethod
    def _is_running(process) -> bool:
        return bool(process and process.poll() is None)

    @staticmethod
    def _terminate(process) -> None:
        if not process:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except Exception:
                process.kill()

    def _start_ffmpeg(self) -> None:
        input_url = f"tcp://127.0.0.1:{self.h264_tcp_port}?listen=1"
        output_url = self.stream_url
        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-i",
            input_url,
            "-an",
            "-c:v",
            "mjpeg",
            "-q:v",
            "7",
            "-f",
            "mpjpeg",
            "-listen",
            "1",
            output_url,
        ]
        self._ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _start_camera(self) -> None:
        out_url = f"tcp://127.0.0.1:{self.h264_tcp_port}"
        camera_cmd = [
            "rpicam-vid",
            "--nopreview",
            "--codec",
            "h264",
            "--profile",
            str(self.profile),
            "--inline",
            "--width",
            str(self.width),
            "--height",
            str(self.height),
            "--framerate",
            str(self.framerate),
            "--shutter",
            str(self.shutter),
            "--denoise",
            str(self.denoise),
            "--sharpness",
            str(self.sharpness),
            "--awb",
            str(self.awb),
            "-t",
            "0",
            "-o",
            out_url,
        ]
        self._camera_process = subprocess.Popen(
            camera_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
