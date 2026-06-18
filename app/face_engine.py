"""Face detection + recognition backend built on OpenCV's bundled models.

Uses:
  - YuNet  (cv2.FaceDetectorYN)   -> fast, accurate face detection + 5 landmarks
  - SFace  (cv2.FaceRecognizerSF) -> 128-d recognition embedding (cosine matching)

Both models are plain ONNX files shipped by the OpenCV Zoo and run through
OpenCV's own DNN backend, so there is NO native build step on Windows.

Isolated here so the recognition backend stays swappable. Every detected face
exposes the same interface the rest of the app relies on:
  - bbox            : np.ndarray [x1, y1, x2, y2]
  - det_score       : float detection confidence
  - normed_embedding: np.ndarray (128,) L2-normalized -> cosine sim = dot product
"""
import os
import threading
import urllib.request
from dataclasses import dataclass

import cv2
import numpy as np

from app.config import settings

MODELS_DIR = os.path.join(settings.data_dir, "models")

_DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
_RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
_DETECTOR_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
_RECOGNIZER_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)


@dataclass
class Face:
    bbox: np.ndarray          # [x1, y1, x2, y2]
    det_score: float
    normed_embedding: np.ndarray
    _row: np.ndarray          # raw YuNet detection row (for alignment)


def _ensure_model(filename: str, url: str) -> str:
    os.makedirs(MODELS_DIR, exist_ok=True)
    path = os.path.join(MODELS_DIR, filename)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        tmp = path + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, path)
    return path


class FaceEngine:
    def __init__(self) -> None:
        self._detector = None
        self._recognizer = None
        self._input_size = (0, 0)
        self._lock = threading.Lock()

    def load(self) -> None:
        """Download (first run only) and initialise the models."""
        if self._detector is not None:
            return
        with self._lock:
            if self._detector is not None:
                return
            det_path = _ensure_model(_DETECTOR_FILE, _DETECTOR_URL)
            rec_path = _ensure_model(_RECOGNIZER_FILE, _RECOGNIZER_URL)
            self._detector = cv2.FaceDetectorYN.create(
                det_path, "", (320, 320),
                score_threshold=settings.min_face_score,
                nms_threshold=0.3, top_k=5000,
            )
            self._recognizer = cv2.FaceRecognizerSF.create(rec_path, "")

    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        """Return a list of detected + embedded faces for a BGR frame."""
        self.load()
        h, w = frame_bgr.shape[:2]
        if (w, h) != self._input_size:
            self._detector.setInputSize((w, h))
            self._input_size = (w, h)

        _, dets = self._detector.detect(frame_bgr)
        faces: list[Face] = []
        if dets is None:
            return faces

        for row in dets:
            x, y, bw, bh = row[:4]
            score = float(row[-1])
            aligned = self._recognizer.alignCrop(frame_bgr, row)
            feat = self._recognizer.feature(aligned).flatten()
            faces.append(Face(
                bbox=np.array([x, y, x + bw, y + bh], dtype=np.float32),
                det_score=score,
                normed_embedding=self.normalize(feat),
                _row=row,
            ))
        return faces

    def largest_face(self, frame_bgr: np.ndarray):
        """Return the single largest detected face, or None."""
        faces = self.detect(frame_bgr)
        if not faces:
            return None
        return max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )

    @staticmethod
    def normalize(vec) -> np.ndarray:
        vec = np.asarray(vec, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec


face_engine = FaceEngine()
