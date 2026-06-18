"""Database engine, session factory and table setup."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# Ensure storage directories exist before SQLite tries to create the file.
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.models_dir, exist_ok=True)
os.makedirs(settings.faces_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """Create tables and run lightweight column migrations."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Add columns introduced after the initial schema; safe to run every startup.
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(employees)"))}
        if "date_of_birth" not in existing:
            conn.execute(text("ALTER TABLE employees ADD COLUMN date_of_birth DATE"))


def get_db():
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
