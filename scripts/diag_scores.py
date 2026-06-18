import numpy as np

from app.face_engine import face_engine

for label, fill in [("black", 0), ("gray200", 200), ("white", 255), ("noise", -1)]:
    if fill == -1:
        rng = np.random.default_rng(0)
        img = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
    else:
        img = np.full((480, 640, 3), fill, np.uint8)
    faces = face_engine.detect(img)
    print(label, "->", [round(f.det_score, 3) for f in faces])
