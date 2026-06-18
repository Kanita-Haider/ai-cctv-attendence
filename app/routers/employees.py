"""Employee CRUD + face enrolment endpoints."""
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
from app.models import Employee, FaceEmbedding
from app.recognizer import recognizer
from app.schemas import EmployeeOut, MessageOut

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _to_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        employee_code=emp.employee_code,
        name=emp.name,
        department=emp.department or "",
        email=emp.email or "",
        active=emp.active,
        date_of_birth=emp.date_of_birth,
        created_at=emp.created_at,
        enrolled_faces=len(emp.embeddings),
    )


def _decode_image(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image file.")
    return img


@router.get("", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return [_to_out(e) for e in db.query(Employee).order_by(Employee.name).all()]


@router.post("", response_model=EmployeeOut)
async def create_employee(
    employee_code: str = Form(...),
    name: str = Form(...),
    department: str = Form(""),
    email: str = Form(""),
    date_of_birth: Optional[str] = Form(default=None),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    if db.query(Employee).filter(Employee.employee_code == employee_code).first():
        raise HTTPException(status_code=409, detail="Employee code already exists.")

    dob: Optional[date] = None
    if date_of_birth:
        try:
            dob = date.fromisoformat(date_of_birth)
        except ValueError:
            raise HTTPException(status_code=422, detail="date_of_birth must be YYYY-MM-DD.")

    emp = Employee(employee_code=employee_code, name=name, department=department, email=email,
                   date_of_birth=dob)
    db.add(emp)
    db.commit()
    db.refresh(emp)

    enrolled = await _enroll_images(emp, images, db)
    if images and enrolled == 0:
        # No usable face in any uploaded photo -> roll back the empty record.
        db.delete(emp)
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="No face detected in the uploaded image(s). Use a clear, front-facing photo.",
        )
    recognizer.reload()
    db.refresh(emp)
    return _to_out(emp)


@router.post("/{employee_id}/faces", response_model=MessageOut)
async def add_faces(
    employee_id: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    enrolled = await _enroll_images(emp, images, db)
    if enrolled == 0:
        raise HTTPException(status_code=422, detail="No face detected in the uploaded image(s).")
    recognizer.reload()
    return MessageOut(message=f"Enrolled {enrolled} face(s).", detail={"enrolled": enrolled})


@router.delete("/{employee_id}", response_model=MessageOut)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    db.delete(emp)
    db.commit()
    recognizer.reload()
    return MessageOut(message="Employee deleted.")


async def _enroll_images(emp: Employee, images: list[UploadFile], db: Session) -> int:
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
        fname = f"{emp.employee_code}_{ts}.jpg"
        path = os.path.join(settings.faces_dir, fname)
        cv2.imwrite(path, img)

        vector = face_engine.normalize(face.normed_embedding).tolist()
        db.add(FaceEmbedding(employee_id=emp.id, vector=json.dumps(vector), image_path=path))
        enrolled += 1

    if enrolled:
        db.commit()
    return enrolled
