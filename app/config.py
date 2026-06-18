"""Application settings, loaded from environment / .env file."""
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
    recognition_threshold: float = 0.363  # cosine similarity for a positive match
    min_face_score: float = 0.7           # minimum YuNet detection confidence

    # Attendance rules
    work_start: str = "09:00"             # HH:MM
    grace_minutes: int = 10
    recognition_cooldown_seconds: int = 60

    # Storage
    data_dir: str = "./data"
    faces_dir: str = "./data/faces"


settings = Settings()
