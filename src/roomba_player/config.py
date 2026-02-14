"""Configuration for roomba-player."""

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "roomba-player"
    telemetry_interval_sec: float = 1.0


settings = Settings()
