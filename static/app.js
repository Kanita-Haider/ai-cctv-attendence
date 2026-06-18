// ---------- tab switching ----------
const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
tabs.forEach((t) => t.addEventListener("click", () => {
  tabs.forEach((x) => x.classList.remove("active"));
  panels.forEach((p) => p.classList.remove("active"));
  t.classList.add("active");
  document.getElementById(t.dataset.tab).classList.add("active");
  if (t.dataset.tab === "attendance") loadAttendance();
  if (t.dataset.tab === "students")   loadStudents();
  if (t.dataset.tab === "analytics")  loadAnalytics();
}));

const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString() : "—";

// ---------- system status ----------
async function pollStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    document.getElementById("dot-camera").classList.toggle("on", s.camera_connected);
    document.getElementById("dot-model").classList.toggle("on", s.model_ready);
    document.getElementById("status-text").textContent =
      `${s.camera_id} · ${s.enrolled_vectors} student(s) enrolled`;
  } catch (_) {}
}

// ---------- live events ----------
async function pollEvents() {
  try {
    const events = await (await fetch("/api/events")).json();
    const list = document.getElementById("event-list");
    if (!events.length) return;
    list.innerHTML = events.map((e) => `
      <li>
        <div class="ev-name">${e.name} <span class="badge ${e.event === "check-in" ? "present" : ""}">${e.event}</span></div>
        <div class="ev-meta">${fmtTime(e.timestamp)} · match ${e.score}</div>
      </li>`).join("");
  } catch (_) {}
}

// ---------- webcam + live recognition ----------
const webcamEl   = document.getElementById("webcam");
const overlayEl  = document.getElementById("overlay");
const captureEl  = document.getElementById("capture-canvas");
const wrapEl     = document.getElementById("webcam-wrap");
const deniedEl   = document.getElementById("webcam-denied");
const waitingEl  = document.getElementById("webcam-waiting");
const overlayCtx = overlayEl.getContext("2d");
const captureCtx = captureEl.getContext("2d");

const STATUS_COLOR = {
  present: "#2dd4bf",
  late:    "#facc15",
  seen:    "#2dd4bf",
  unknown: "#ef4444",
};

function syncCanvasSize() {
  const w = webcamEl.videoWidth  || webcamEl.clientWidth;
  const h = webcamEl.videoHeight || webcamEl.clientHeight;
  if (overlayEl.width !== w || overlayEl.height !== h) {
    overlayEl.width   = w;
    overlayEl.height  = h;
    captureEl.width   = w;
    captureEl.height  = h;
  }
}

function drawDetections(detections) {
  overlayCtx.clearRect(0, 0, overlayEl.width, overlayEl.height);
  for (const d of detections) {
    const [x1, y1, x2, y2] = d.bbox;
    const color = STATUS_COLOR[d.status] || STATUS_COLOR.unknown;
    const w = x2 - x1, h = y2 - y1;

    // box
    overlayCtx.strokeStyle = color;
    overlayCtx.lineWidth   = 2;
    overlayCtx.strokeRect(x1, y1, w, h);

    // label background
    const ageStr   = d.age != null ? ` • ${d.age}` : "";
    const clsStr   = d.class_section ? ` [${d.class_section}]` : "";
    const scoreStr = d.status !== "unknown" ? ` (${d.score})` : "";
    const label    = `${d.name}${ageStr}${clsStr}${scoreStr}`;

    overlayCtx.font         = "bold 13px system-ui, sans-serif";
    const textW = overlayCtx.measureText(label).width + 10;
    const boxH  = 20;
    const labelY = y1 > boxH ? y1 - boxH : y2;

    overlayCtx.fillStyle = color;
    overlayCtx.fillRect(x1, labelY, textW, boxH);

    overlayCtx.fillStyle = d.status === "unknown" ? "#fff" : "#042f2a";
    overlayCtx.fillText(label, x1 + 5, labelY + 14);
  }
}

let _capturing = false;

async function captureAndProcess() {
  if (_capturing || webcamEl.readyState < 2) return;
  _capturing = true;
  try {
    syncCanvasSize();
    captureCtx.drawImage(webcamEl, 0, 0, captureEl.width, captureEl.height);
    // strip the "data:image/jpeg;base64," prefix
    const b64 = captureEl.toDataURL("image/jpeg", 0.75).split(",")[1];
    const res  = await fetch("/api/stream/frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame: b64 }),
    });
    if (res.ok) {
      const { detections } = await res.json();
      drawDetections(detections);
    }
  } catch (_) {
    // network hiccup — silently skip this frame
  } finally {
    _capturing = false;
  }
}

async function startWebcam() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
    });
    webcamEl.srcObject = stream;
    webcamEl.addEventListener("loadedmetadata", () => {
      syncCanvasSize();
      waitingEl.style.display = "none";
      wrapEl.style.display    = "block";
    });
    setInterval(captureAndProcess, 400);
  } catch (err) {
    waitingEl.style.display = "none";
    deniedEl.style.display  = "flex";
  }
}

startWebcam();

// ---------- attendance ----------
async function loadAttendance() {
  const date = document.getElementById("att-date").value;
  const url = "/api/attendance" + (date ? `?date=${date}` : "");
  document.getElementById("att-export").href =
    "/api/attendance/export.csv" + (date ? `?date=${date}` : "");
  const rows = await (await fetch(url)).json();
  const body = document.getElementById("att-body");
  body.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${r.student_id}</td>
      <td>${r.name}</td>
      <td>${r.class_section || ""}</td>
      <td>${fmtTime(r.check_in)}</td>
      <td>${fmtTime(r.check_out)}</td>
      <td><span class="badge ${r.status}">${r.status}</span></td>
    </tr>`).join("") : `<tr><td colspan="6" class="muted">No records.</td></tr>`;
}
document.getElementById("att-refresh").addEventListener("click", loadAttendance);
document.getElementById("att-date").addEventListener("change", loadAttendance);

// ---------- students ----------
async function loadStudents() {
  const stus = await (await fetch("/api/students")).json();
  const body = document.getElementById("stu-body");
  body.innerHTML = stus.length ? stus.map((s) => `
    <tr>
      <td>${s.student_id}</td>
      <td>${s.name}</td>
      <td>${s.class_section || ""}</td>
      <td>${s.age != null ? s.age : "—"}</td>
      <td>${s.enrolled_faces}</td>
      <td><button class="del" data-id="${s.id}">Delete</button></td>
    </tr>`).join("") : `<tr><td colspan="6" class="muted">None yet.</td></tr>`;
  body.querySelectorAll(".del").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Delete this student and their face data?")) return;
    await fetch(`/api/students/${b.dataset.id}`, { method: "DELETE" });
    loadStudents();
  }));
}
document.getElementById("stu-refresh").addEventListener("click", loadStudents);

// ---------- enrollment ----------
document.getElementById("enroll-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = document.getElementById("enroll-msg");
  msg.className = "msg"; msg.textContent = "Processing…";
  const fd = new FormData(ev.target);
  try {
    const res = await fetch("/api/students", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Enrollment failed.");
    msg.className = "msg ok";
    msg.textContent = `✓ Enrolled ${data.name} (${data.student_id}) with ${data.enrolled_faces} face(s).`;
    ev.target.reset();
  } catch (err) {
    msg.className = "msg err";
    msg.textContent = "✗ " + err.message;
  }
});

// ---------- analytics ----------
let chartDaily = null;
let chartDonut = null;

function applyChartDefaults() {
  Chart.defaults.color = "#e6edf3";
  Chart.defaults.borderColor = "#283546";
  Chart.defaults.font.family = "system-ui, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.font.size = 12;
}

async function loadAnalytics() {
  applyChartDefaults();
  const [summary, daily, ranking] = await Promise.all([
    fetch("/api/analytics/summary").then((r) => r.json()),
    fetch("/api/analytics/daily").then((r) => r.json()),
    fetch("/api/analytics/ranking").then((r) => r.json()),
  ]);

  document.getElementById("kpi-total").textContent   = summary.total;
  document.getElementById("kpi-present").textContent = summary.present;
  document.getElementById("kpi-late").textContent    = summary.late;
  document.getElementById("kpi-absent").textContent  = summary.absent;

  const labels  = daily.map((d) => d.date.slice(5));
  const present = daily.map((d) => d.present);
  const late    = daily.map((d) => d.late);

  if (chartDaily) chartDaily.destroy();
  chartDaily = new Chart(document.getElementById("chart-daily"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "On-Time", data: present, backgroundColor: "rgba(45,212,191,.75)", borderRadius: 4, stack: "a" },
        { label: "Late",    data: late,    backgroundColor: "rgba(250,204,21,.65)",  borderRadius: 4, stack: "a" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { position: "top" } },
      scales: {
        x: { grid: { color: "#283546" } },
        y: { grid: { color: "#283546" }, beginAtZero: true, ticks: { stepSize: 1 } },
      },
    },
  });

  const onTime = summary.present, lateN = summary.late, absentN = summary.absent;
  if (chartDonut) chartDonut.destroy();
  chartDonut = new Chart(document.getElementById("chart-donut"), {
    type: "doughnut",
    data: {
      labels: ["On-Time", "Late", "Absent"],
      datasets: [{
        data: [onTime, lateN, absentN],
        backgroundColor: ["rgba(45,212,191,.8)", "rgba(250,204,21,.8)", "rgba(239,68,68,.7)"],
        borderWidth: 2, borderColor: "#18222e",
      }],
    },
    options: { responsive: true, cutout: "65%", plugins: { legend: { display: false } } },
  });

  document.getElementById("donut-legend").innerHTML = [
    ["#2dd4bf", "On-Time", onTime],
    ["#facc15", "Late",    lateN],
    ["#ef4444", "Absent",  absentN],
  ].map(([color, label, n]) =>
    `<span><i class="legend-dot" style="background:${color}"></i>${label} (${n})</span>`
  ).join("");

  const body = document.getElementById("ranking-body");
  body.innerHTML = ranking.length ? ranking.map((r) => `
    <tr>
      <td>${r.rank}</td><td>${r.name}</td><td>${r.class_section || "—"}</td>
      <td>${r.attended}</td><td>${r.on_time}</td><td>${r.late}</td>
      <td>${r.rate}%<span class="rate-bar-wrap"><span class="rate-bar" style="width:${r.rate}%"></span></span></td>
    </tr>`).join("") : `<tr><td colspan="7" class="muted">No data yet.</td></tr>`;
}

// ---------- init ----------
document.getElementById("att-date").value = new Date().toISOString().slice(0, 10);
pollStatus(); pollEvents();
setInterval(pollStatus, 4000);
setInterval(pollEvents, 2500);
