"""Browser-driven frame processing endpoint.

Replaces the old server-side MJPEG stream.  The browser captures webcam
frames, encodes them as base64 JPEG, and POSTs them here.  We run the
full detect → recognise → log pipeline and return JSON detections for the
browser to draw on its overlay canvas.
"""
import base64

import cv2
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app.face_engine import face_engine
from app.recognizer import recognizer
from app.worker import worker

router = APIRouter(tags=["stream"])


class FrameIn(BaseModel):
    frame: str   # base64-encoded JPEG (no data-URL prefix)


@router.post("/api/stream/frame")
async def process_frame(body: FrameIn):
    """Decode a browser webcam frame, detect + identify faces, log attendance."""
    try:
        raw = base64.b64decode(body.frame)
    except Exception:
        return {"detections": []}

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"detections": []}

    faces = face_engine.detect(img)
    worker.model_ready = True

    detections = []
    for f in faces:
        student_db_id, score = recognizer.identify(f.normed_embedding)
        x1, y1, x2, y2 = (int(v) for v in f.bbox)

        if student_db_id is not None:
            name, status, age, class_section = worker.log_attendance(student_db_id, score)
        else:
            name, status, age, class_section = "Unknown", "unknown", None, ""

        detections.append({
            "bbox": [x1, y1, x2, y2],
            "name": name,
            "age": age,
            "class_section": class_section,
            "status": status,
            "score": round(score, 3),
        })

    return {"detections": detections}
