"""Attendance event tracker: debounce, check-in/out logging, status.

The background camera thread has been removed — frames now arrive via the
browser webcam and POST /api/stream/frame.  This module keeps only the
stateful pieces shared across requests: the debounce map, the event deque,
and the late-check helper.
"""
import threading
import time
from collections import deque
from datetime import date, datetime, time as dtime

from app.config import settings
from app.database import SessionLocal
from app.models import Attendance, Student
from app.recognizer import recognizer
from app.schemas import _compute_age


class AttendanceWorker:
    def __init__(self) -> None:
        self._last_logged: dict[int, float] = {}
        self._lock = threading.Lock()
        self.recent_events: deque = deque(maxlen=50)
        self.model_ready: bool = False   # set True after first successful detect

    def status(self) -> dict:
        return {
            "camera_connected": True,   # browser drives the camera now
            "model_ready": self.model_ready,
            "camera_id": settings.camera_id,
            "enrolled_vectors": len(recognizer._student_ids),
        }

    def _is_late(self, now: datetime) -> bool:
        hh, mm = settings.work_start.split(":")
        threshold = int(hh) * 60 + int(mm) + settings.grace_minutes
        return (now.hour * 60 + now.minute) > threshold

    def log_attendance(self, student_db_id: int, score: float):
        """Debounced check-in / check-out. Returns (name, status, age, class_section)."""
        now_mono = time.monotonic()
        with self._lock:
            last = self._last_logged.get(student_db_id, 0.0)
            within_cooldown = (now_mono - last) < settings.recognition_cooldown_seconds

        db = SessionLocal()
        try:
            stu = db.get(Student, student_db_id)
            if stu is None:
                return "Unknown", "unknown", None, ""

            name = stu.name
            age = _compute_age(stu.date_of_birth)
            class_section = stu.class_section or ""

            if within_cooldown:
                return name, "seen", age, class_section

            with self._lock:
                self._last_logged[student_db_id] = now_mono

            today = date.today()
            now = datetime.now()
            rec = (
                db.query(Attendance)
                .filter(Attendance.employee_id == student_db_id, Attendance.date == today)
                .first()
            )
            if rec is None:
                status = "late" if self._is_late(now) else "present"
                rec = Attendance(
                    employee_id=student_db_id, date=today,
                    check_in=now, check_out=now,
                    status=status, camera_id=settings.camera_id,
                )
                db.add(rec)
                event = "check-in"
            else:
                rec.check_out = now
                status = rec.status
                event = "check-out"
            db.commit()

            self.recent_events.appendleft({
                "student_db_id": student_db_id,
                "name": name,
                "event": event,
                "score": round(score, 3),
                "timestamp": now.isoformat(timespec="seconds"),
            })
            return name, status, age, class_section
        finally:
            db.close()


worker = AttendanceWorker()
