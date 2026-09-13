"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://lfr:lfr_dev_password@db:5432/lfr"
    data_dir: str = "/data"

    # Face pipeline tuning
    det_threshold: float = 0.5
    min_face_size: int = 80
    match_threshold: float = 0.42
    frame_skip: int = 5
    alert_cooldown_seconds: int = 30
    consensus_frames: int = 3
    consensus_window_seconds: int = 5

    # Quality gate
    blur_reject_below: float = 0.15

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
