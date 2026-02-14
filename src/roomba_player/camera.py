"""Camera streaming helpers based on rpicam-vid + ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import threading


class CameraService:
    """On-demand camera stream pipeline.

    Stream chain (per HTTP client):
    rpicam-vid (H264 stdout) -> ffmpeg (MJPEG stdout) -> HTTP response
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
        self._lock = threading.Lock()
        self._active_camera = None
        self._active_ffmpeg = None

    @property
    def stream_url(self) -> str:
        return f"http://{self.http_bind_host}:{self.http_port}{self.http_path}"

    def start_if_enabled(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "started": False, "reason": "disabled", "stream_url": ""}

        missing = []
        if shutil.which("rpicam-vid") is None:
            missing.append("rpicam-vid")
        if shutil.which("ffmpeg") is None:
            missing.append("ffmpeg")
        if missing:
            return {
                "enabled": True,
                "started": False,
                "reason": f"missing_binaries:{','.join(missing)}",
                "stream_url": "/camera/stream",
            }

        return {
            "enabled": True,
            "started": True,
            "reason": "ready_on_demand",
            "stream_url": "/camera/stream",
        }

    def open_stream_processes(self):
        """Create per-request stream processes.

        Returns `(camera_proc, ffmpeg_proc)` where ffmpeg stdout is MJPEG bytes.
        """
        with self._lock:
            self._terminate_pair(self._active_camera, self._active_ffmpeg)

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
                "-",
            ]

            camera_proc = subprocess.Popen(
                camera_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "mjpeg",
                "-q:v",
                "7",
                "-f",
                "mpjpeg",
                "pipe:1",
            ]

            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=camera_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            self._active_camera = camera_proc
            self._active_ffmpeg = ffmpeg_proc
            return camera_proc, ffmpeg_proc

    def stop(self) -> None:
        with self._lock:
            self._terminate_pair(self._active_camera, self._active_ffmpeg)
            self._active_camera = None
            self._active_ffmpeg = None

    @staticmethod
    def _terminate_pair(camera_proc, ffmpeg_proc) -> None:
        for proc in (ffmpeg_proc, camera_proc):
            if not proc:
                continue
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except Exception:
                    if proc.poll() is None:
                        proc.kill()
