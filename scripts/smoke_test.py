"""Smoke test for the enrollment HTTP path against a running server."""
import json
import urllib.error
import urllib.request

import cv2
import numpy as np

BASE = "http://127.0.0.1:8000"
BOUNDARY = "----testboundary12345"


def _field(name, val):
    return (
        f"--{BOUNDARY}\r\nContent-Disposition: form-data; "
        f'name="{name}"\r\n\r\n{val}\r\n'
    ).encode()


def _file(name, fname, data):
    head = (
        f"--{BOUNDARY}\r\nContent-Disposition: form-data; "
        f'name="{name}"; filename="{fname}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    return head + data + b"\r\n"


def main():
    blank = np.full((480, 640, 3), 200, np.uint8)
    _, buf = cv2.imencode(".jpg", blank)
    img = buf.tobytes()

    body = (
        _field("employee_code", "E001")
        + _field("name", "Test User")
        + _field("department", "QA")
        + _field("email", "")
        + _file("images", "blank.jpg", img)
        + f"--{BOUNDARY}--\r\n".encode()
    )

    req = urllib.request.Request(
        BASE + "/api/employees",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req)
        print("UNEXPECTED OK:", r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print("ENROLL no-face -> HTTP", e.code, e.read().decode())

    emps = json.loads(urllib.request.urlopen(BASE + "/api/employees").read())
    print("employees after failed enroll:", emps)


if __name__ == "__main__":
    main()
