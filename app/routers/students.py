"""Student CRUD + face enrolment endpoints."""
import json
import os
from datetime import date, datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.face_engine import face_engine
from app.models import FaceEmbedding, Student
from app.recognizer import recognizer
from app.schemas import MessageOut, StudentOut

router = APIRouter(prefix="/api/students", tags=["students"])


def _to_out(stu: Student) -> StudentOut:
    return StudentOut(
        id=stu.id,
        student_id=stu.student_id,
        name=stu.name,
        class_section=stu.class_section or "",
        email=stu.email or "",
        active=stu.active,
        date_of_birth=stu.date_of_birth,
        created_at=stu.created_at,
        enrolled_faces=len(stu.embeddings),
    )


def _decode_image(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image file.")
    return img


@router.get("", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db)):
    return [_to_out(s) for s in db.query(Student).order_by(Student.name).all()]


@router.post("", response_model=StudentOut)
async def create_student(
    student_id: str = Form(...),
    name: str = Form(...),
    class_section: str = Form(""),
    email: str = Form(""),
    date_of_birth: Optional[str] = Form(default=None),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    if db.query(Student).filter(Student.student_id == student_id).first():
        raise HTTPException(status_code=409, detail="Student ID already exists.")

    dob: Optional[date] = None
    if date_of_birth:
        try:
            dob = date.fromisoformat(date_of_birth)
        except ValueError:
            raise HTTPException(status_code=422, detail="date_of_birth must be YYYY-MM-DD.")

    stu = Student(student_id=student_id, name=name, class_section=class_section,
                  email=email, date_of_birth=dob)
    db.add(stu)
    db.commit()
    db.refresh(stu)

    enrolled = await _enroll_images(stu, images, db)
    if images and enrolled == 0:
        db.delete(stu)
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="No face detected in the uploaded image(s). Use a clear, front-facing photo.",
        )
    recognizer.reload()
    db.refresh(stu)
    return _to_out(stu)


@router.post("/{student_db_id}/faces", response_model=MessageOut)
async def add_faces(
    student_db_id: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    stu = db.get(Student, student_db_id)
    if stu is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    enrolled = await _enroll_images(stu, images, db)
    if enrolled == 0:
        raise HTTPException(status_code=422, detail="No face detected in the uploaded image(s).")
    recognizer.reload()
    return MessageOut(message=f"Enrolled {enrolled} face(s).", detail={"enrolled": enrolled})


@router.delete("/{student_db_id}", response_model=MessageOut)
def delete_student(student_db_id: int, db: Session = Depends(get_db)):
    stu = db.get(Student, student_db_id)
    if stu is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    db.delete(stu)
    db.commit()
    recognizer.reload()
    return MessageOut(message="Student deleted.")


async def _enroll_images(stu: Student, images: list[UploadFile], db: Session) -> int:
    """Detect the largest face in each image, store its embedding. Returns count."""
    enrolled = 0
    for upload in images:
        raw = await upload.read()
        if not raw:
            continue
        img = _decode_image(raw)
        face = face_engine.largest_face(img)
        if face is None:
            continue

        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        fname = f"{stu.student_id}_{ts}.jpg"
        path = os.path.join(settings.faces_dir, fname)
        cv2.imwrite(path, img)

        vector = face_engine.normalize(face.normed_embedding).tolist()
        db.add(FaceEmbedding(employee_id=stu.id, vector=json.dumps(vector), image_path=path))
        enrolled += 1

    if enrolled:
        db.commit()
    return enrolled
