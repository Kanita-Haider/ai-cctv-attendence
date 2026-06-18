"""Attendance query, live-event feed, CSV export, and analytics endpoints."""
import csv
import io
from datetime import date as date_cls, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attendance, Student
from app.schemas import AttendanceOut, EventOut
from app.worker import worker

router = APIRouter(prefix="/api", tags=["attendance"])


def _parse_date(value: str | None) -> date_cls:
    if not value:
        return date_cls.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _query(db: Session, day: date_cls):
    rows = (
        db.query(Attendance, Student)
        .join(Student, Attendance.employee_id == Student.id)
        .filter(Attendance.date == day)
        .order_by(Attendance.check_in)
        .all()
    )
    return rows


@router.get("/attendance", response_model=list[AttendanceOut])
def get_attendance(date: str | None = Query(default=None), db: Session = Depends(get_db)):
    day = _parse_date(date)
    out = []
    for att, stu in _query(db, day):
        out.append(AttendanceOut(
            id=att.id,
            student_db_id=stu.id,
            student_id=stu.student_id,
            name=stu.name,
            class_section=stu.class_section or "",
            date=att.date,
            check_in=att.check_in,
            check_out=att.check_out,
            status=att.status,
            camera_id=att.camera_id or "",
        ))
    return out


@router.get("/attendance/export.csv")
def export_csv(date: str | None = Query(default=None), db: Session = Depends(get_db)):
    day = _parse_date(date)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Student ID", "Name", "Class/Section", "Date",
                     "Check In", "Check Out", "Status", "Camera"])
    for att, stu in _query(db, day):
        writer.writerow([
            stu.student_id, stu.name, stu.class_section or "", att.date.isoformat(),
            att.check_in.isoformat(sep=" ", timespec="seconds") if att.check_in else "",
            att.check_out.isoformat(sep=" ", timespec="seconds") if att.check_out else "",
            att.status, att.camera_id or "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="attendance_{day.isoformat()}.csv"'}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    today = date_cls.today()
    total = db.query(func.count(Student.id)).filter(Student.active == 1).scalar() or 0
    rows = db.query(Attendance).filter(Attendance.date == today).all()
    present = sum(1 for r in rows if r.status == "present")
    late = sum(1 for r in rows if r.status == "late")
    absent = max(0, total - present - late)
    return {"date": today.isoformat(), "total": total, "present": present, "late": late, "absent": absent}


@router.get("/analytics/daily")
def analytics_daily(db: Session = Depends(get_db)):
    today = date_cls.today()
    result = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        rows = db.query(Attendance).filter(Attendance.date == day).all()
        result.append({
            "date": day.isoformat(),
            "present": sum(1 for r in rows if r.status == "present"),
            "late": sum(1 for r in rows if r.status == "late"),
        })
    return result


@router.get("/analytics/ranking")
def analytics_ranking(db: Session = Depends(get_db)):
    students = db.query(Student).filter(Student.active == 1).all()
    today = date_cls.today()
    window_start = today - timedelta(days=29)
    total_days = 30

    ranking = []
    for stu in students:
        rows = (
            db.query(Attendance)
            .filter(Attendance.employee_id == stu.id, Attendance.date >= window_start)
            .all()
        )
        attended = len(rows)
        on_time = sum(1 for r in rows if r.status == "present")
        late = attended - on_time
        rate = round(attended / total_days * 100, 1)
        ranking.append({
            "id": stu.id,
            "student_id": stu.student_id,
            "name": stu.name,
            "class_section": stu.class_section or "",
            "attended": attended,
            "on_time": on_time,
            "late": late,
            "rate": rate,
        })

    ranking.sort(key=lambda x: (-x["rate"], -x["on_time"]))
    for i, r in enumerate(ranking):
        r["rank"] = i + 1
    return ranking


@router.get("/events", response_model=list[EventOut])
def recent_events():
    return list(worker.recent_events)


@router.get("/status")
def system_status():
    return worker.status()
