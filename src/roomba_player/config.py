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


settings = Settings()
