"""Configuration for roomba-player."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROOMBA_PLAYER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "roomba-player"
    telemetry_interval_sec: float = 1.0
    roomba_serial_port: str = "/dev/ttyUSB0"
    roomba_baudrate: int = 115200
    roomba_timeout_sec: float = 1.0
    camera_stream_enabled: bool = False
    camera_width: int = 800
    camera_height: int = 600
    camera_framerate: int = 15
    camera_profile: str = "high"
    camera_shutter: int = 12000
    camera_denoise: str = "cdn_fast"
    camera_sharpness: float = 1.1
    camera_awb: str = "auto"
    camera_h264_tcp_port: int = 9100
    camera_http_bind_host: str = "0.0.0.0"
    camera_http_port: int = 8081
    camera_http_path: str = "/stream.mjpg"
    plan_default_path: str = ""
    odometry_history_path: str = "bdd/odometry_history.jsonl"
    odometry_source: str = "encoders"
    odometry_linear_scale: float = 1.0
    odometry_angular_scale: float = 1.0


settings = Settings()
