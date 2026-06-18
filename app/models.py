"""SQLAlchemy ORM models."""
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Student(Base):
    __tablename__ = "employees"   # keep physical table name to avoid FK cascade issues

    id = Column(Integer, primary_key=True)
    student_id = Column("employee_code", String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    class_section = Column("department", String, default="")
    email = Column(String, default="")
    active = Column(Integer, default=1)
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    embeddings = relationship(
        "FaceEmbedding", back_populates="student", cascade="all, delete-orphan"
    )
    attendance = relationship(
        "Attendance", back_populates="student", cascade="all, delete-orphan"
    )


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    vector = Column(Text, nullable=False)   # JSON-encoded list[float]
    image_path = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="embeddings")


class Attendance(Base):
    """One row per student per day; check_out is updated on every sighting."""

    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    date = Column(Date, index=True)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    status = Column(String, default="present")   # present | late
    camera_id = Column(String, default="")

    student = relationship("Student", back_populates="attendance")
