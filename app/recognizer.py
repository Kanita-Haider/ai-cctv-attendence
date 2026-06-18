"""In-memory nearest-neighbour index over enrolled face embeddings.

Embeddings are L2-normalized, so cosine similarity is a plain dot product.
For an MVP-scale roster (hundreds–low thousands of faces) a single matrix
multiply per face is more than fast enough.
"""
import json
import threading

import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.models import FaceEmbedding


class Recognizer:
    def __init__(self) -> None:
        self._matrix = None          # (N, 512) float32
        self._student_ids: list[int] = []
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> int:
        """Rebuild the index from the database. Returns the number of vectors."""
        from app.database import init_db

        init_db()
        db = SessionLocal()
        try:
            rows = db.query(FaceEmbedding).all()
            vectors, ids = [], []
            for row in rows:
                vectors.append(np.asarray(json.loads(row.vector), dtype=np.float32))
                ids.append(row.employee_id)
        finally:
            db.close()

        with self._lock:
            if vectors:
                self._matrix = np.vstack(vectors)
                self._student_ids = ids
            else:
                self._matrix = None
                self._student_ids = []
        return len(ids)

    def identify(self, embedding) -> tuple[int | None, float]:
        """Return (student db id, score). id is None below threshold."""
        with self._lock:
            matrix = self._matrix
            ids = self._student_ids
        if matrix is None:
            return None, 0.0

        emb = np.asarray(embedding, dtype=np.float32)
        sims = matrix @ emb            # both sides are unit vectors
        idx = int(np.argmax(sims))
        score = float(sims[idx])
        if score >= settings.recognition_threshold:
            return ids[idx], score
        return None, score


recognizer = Recognizer()
