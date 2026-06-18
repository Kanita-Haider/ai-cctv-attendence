"""Application settings, loaded from environment / .env file."""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Monipur High School Attendance"
    database_url: str = "sqlite:///./data/attendance.db"

    # Camera
    rtsp_url: str = "0"          # RTSP URL, or "0" for local webcam
    camera_id: str = "CAM-1"

    # Face recognition (SFace cosine match; recommended threshold ~0.363)
    recognition_threshold: float = 0.363
    min_face_score: float = 0.7

    # Attendance rules
    work_start: str = "09:00"             # HH:MM
    grace_minutes: int = 10
    recognition_cooldown_seconds: int = 60

    # Storage — all three are overridden by env vars on Render
    data_dir: str = "./data"
    models_dir: str = "./data/models"   # MODELS_DIR env var
    faces_dir: str = "./data/faces"     # FACES_DIR env var

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        """Accept a plain file path (as Render sets it) and convert to a SQLAlchemy URL."""
        if isinstance(v, str) and not v.startswith(("sqlite://", "postgresql://", "mysql://")):
            return f"sqlite:///{v}"
        return v


settings = Settings()
