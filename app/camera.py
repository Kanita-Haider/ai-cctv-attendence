"""Threaded RTSP/webcam capture that always serves the most recent frame.

A dedicated reader thread keeps draining the stream so the recognition loop
never processes stale buffered frames, and reconnects automatically if the
CCTV stream drops.
"""
import threading
import time

import cv2

from app.config import settings


class CameraStream:
    def __init__(self, src=None) -> None:
        src = settings.rtsp_url if src is None else src
        # Allow "0", "1" ... to mean a local webcam index.
        self.src = int(src) if isinstance(src, str) and src.isdigit() else src
        self.cap = None
        self.frame = None
        self.connected = False
        self.running = False
        self._lock = threading.Lock()
        self._thread = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _open(self):
        cap = cv2.VideoCapture(self.src)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _update(self) -> None:
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self.cap = self._open()
                if not self.cap.isOpened():
                    self.connected = False
                    time.sleep(2.0)        # back off before retrying
                    continue
            ok, frame = self.cap.read()
            if not ok:
                self.connected = False
                self.cap.release()
                self.cap = None
                time.sleep(1.0)
                continue
            self.connected = True
            with self._lock:
                self.frame = frame

    def read(self):
        with self._lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self) -> None:
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
