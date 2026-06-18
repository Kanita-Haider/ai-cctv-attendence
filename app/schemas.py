"""Pydantic response/request schemas."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


def _compute_age(dob: Optional[date]) -> Optional[int]:
    if dob is None:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    name: str
    class_section: str = ""
    email: str = ""
    active: int = 1
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    created_at: Optional[datetime] = None
    enrolled_faces: int = 0

    @model_validator(mode="after")
    def _fill_age(self):
        self.age = _compute_age(self.date_of_birth)
        return self


class AttendanceOut(BaseModel):
    id: int
    student_db_id: int
    student_id: str
    name: str
    class_section: str = ""
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: str
    camera_id: str = ""


class EventOut(BaseModel):
    student_db_id: Optional[int] = None
    name: str
    event: str          # check-in | check-out | unknown
    score: float
    timestamp: datetime


class MessageOut(BaseModel):
    ok: bool = True
    message: str = ""
    detail: Optional[dict] = None
