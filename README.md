# 🎥 AI CCTV Time & Attendance (Face Recognition)

A self-hosted attendance system that watches an **RTSP CCTV camera**, recognizes
enrolled employees in real time using **face recognition**, and automatically logs
**check-in / check-out** times to a database — with a web dashboard for enrollment,
a live annotated video feed, attendance reports, and CSV export.

| Layer            | Technology |
|------------------|------------|
| Backend / API    | FastAPI + Uvicorn |
| Computer vision  | OpenCV (capture + DNN) |
| Face detection   | **YuNet** (`cv2.FaceDetectorYN`) — fast CNN detector + 5 landmarks |
| Face recognition | **SFace** (`cv2.FaceRecognizerSF`) — 128-d embeddings, cosine matching |
| Matching         | Cosine similarity over an in-memory embedding index (NumPy) |
| Database         | SQLAlchemy + SQLite (swap `DATABASE_URL` for Postgres/MySQL) |
| Frontend         | Vanilla HTML/CSS/JS dashboard |

> **Why YuNet + SFace?** Both ship with OpenCV and run through its own DNN backend,
> so there's **no native compiler step on Windows** (InsightFace/dlib both require
> Visual C++ Build Tools to compile). They're accurate, lightweight (~37 MB total),
> CPU-friendly, and the two ONNX model files auto-download on first run. The whole
> engine is wrapped in [`app/face_engine.py`](app/face_engine.py) — swap in
> InsightFace/ArcFace later by changing only that file.

---

## How it works

```
RTSP camera ──► CameraStream (threaded, always-latest frame)
                     │
                     ▼
            AttendanceWorker loop ──► FaceEngine.detect()  (YuNet + SFace)
                     │                      │
                     │                      ▼
                     │              Recognizer.identify()  (cosine match)
                     │                      │
                     ├── draw boxes/labels ─┘
                     │        └──► /video_feed  (MJPEG → dashboard)
                     ▼
            log/update Attendance row  (debounced per person)
                     └──► SQLite ──► /api/attendance, CSV export
```

- **First sighting of the day** → creates an attendance row (`check_in`), flagged
  `late` if after `WORK_START + GRACE_MINUTES`.
- **Subsequent sightings** → update `check_out`.
- A per-person **cooldown** (`RECOGNITION_COOLDOWN_SECONDS`) prevents duplicate logging.

---

## Setup

Requires **Python 3.9+**. No C++ compiler needed.

```powershell
cd D:\ai-cctv-attendance

# 1. Virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configuration
copy .env.example .env
#   then edit .env — set RTSP_URL to your camera (or leave "0" to use a webcam)
```

The first run downloads the two ONNX model files (YuNet + SFace, ~37 MB) into
`data/models/` automatically — this needs internet access once.

---

## Run

```powershell
python run.py
```

Open **http://localhost:8000** in your browser.

1. **Enroll** tab → add each employee with a clear, front-facing photo (you can
   upload several photos per person for better accuracy).
2. **Live View** tab → annotated CCTV feed + a rolling list of recognitions.
3. **Attendance** tab → daily records, pick a date, **Export CSV**.
4. **Employees** tab → manage the roster.

---

## Configuration (`.env`)

| Key | Default | Meaning |
|-----|---------|---------|
| `RTSP_URL` | `0` | RTSP stream URL, e.g. `rtsp://user:pass@192.168.1.10:554/Streaming/Channels/101`. `0` = local webcam. |
| `CAMERA_ID` | `CAM-1` | Label stored with each attendance record. |
| `RECOGNITION_THRESHOLD` | `0.363` | SFace cosine cutoff for a match. ↑ = stricter (fewer false matches). |
| `MIN_FACE_SCORE` | `0.7` | Minimum YuNet detection confidence to consider a face. |
| `WORK_START` | `09:00` | Office start time for late detection. |
| `GRACE_MINUTES` | `10` | Minutes after `WORK_START` before "late". |
| `RECOGNITION_COOLDOWN_SECONDS` | `60` | Min gap before re-logging the same person. |

---

## API reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/` | Dashboard |
| `GET`  | `/video_feed` | MJPEG annotated live stream |
| `GET`  | `/api/status` | Camera/model/enrollment status |
| `GET`  | `/api/employees` | List employees |
| `POST` | `/api/employees` | Create employee + enroll face(s) *(multipart)* |
| `POST` | `/api/employees/{id}/faces` | Add more face photos |
| `DELETE` | `/api/employees/{id}` | Remove employee + face data |
| `GET`  | `/api/attendance?date=YYYY-MM-DD` | Attendance for a day |
| `GET`  | `/api/attendance/export.csv?date=...` | CSV export |
| `GET`  | `/api/events` | Recent live recognitions |

Interactive docs at **http://localhost:8000/docs**.

---

## Project structure

```
ai-cctv-attendance/
├── app/
│   ├── config.py        # settings (.env)
│   ├── database.py      # engine + session + init
│   ├── models.py        # Employee, FaceEmbedding, Attendance
│   ├── schemas.py       # Pydantic I/O models
│   ├── face_engine.py   # YuNet + SFace wrapper (detect + embed)
│   ├── recognizer.py    # in-memory cosine match index
│   ├── camera.py        # threaded RTSP/webcam capture
│   ├── worker.py        # recognition + attendance loop + MJPEG frames
│   ├── main.py          # FastAPI app + lifespan
│   └── routers/         # employees, attendance, stream
├── static/              # dashboard (HTML/CSS/JS)
├── data/                # SQLite DB + enrolled face images (auto-created)
├── requirements.txt
├── .env.example
└── run.py
```

---

## Production notes

- **Database**: SQLite is fine for a single site. For multiple locations, point
  `DATABASE_URL` at PostgreSQL.
- **Multiple cameras**: the worker handles one stream; run one process per camera
  with a distinct `CAMERA_ID` (and a shared database), or extend `AttendanceWorker`
  to manage a list of `CameraStream`s.
- **Scaling the face index**: brute-force NumPy matching handles thousands of
  faces easily. For tens of thousands, swap `Recognizer` for FAISS/hnswlib.
- **Liveness / anti-spoofing**: this MVP does not detect photo/video spoofing — add
  a liveness model before using it for high-security access control.
- **Privacy & compliance**: biometric data is regulated (GDPR/BIPA/local law).
  Obtain consent, secure `data/`, and define a retention policy before deployment.
- **Security**: there is no auth on the dashboard yet — put it behind a reverse
  proxy with authentication, or add FastAPI auth, before exposing it.
```
