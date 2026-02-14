"""FastAPI entrypoint."""

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from .config import settings
from .roomba import RoombaOI
from .telemetry import get_telemetry_snapshot
from .ws import control_stream, telemetry_stream

app = FastAPI(title="roomba-player", version="0.1.0")

HOME_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>roomba-player</title>
    <style>
      body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; line-height: 1.4; max-width: 900px; }
      code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 4px; }
      .btn { display: inline-block; margin-top: 1rem; padding: 0.7rem 1rem; border-radius: 8px; border: 1px solid #222; text-decoration: none; color: #111; }
    </style>
  </head>
  <body>
    <h1>roomba-player</h1>
    <p>Control, monitor and auto-pilot a Roomba from Raspberry Pi over HTTP/WebSocket.</p>

    <h2>Current API</h2>
    <ul>
      <li><code>GET /health</code></li>
      <li><code>GET /telemetry</code></li>
      <li><code>WS /ws/telemetry</code></li>
      <li><code>WS /ws/control</code></li>
      <li><code>GET /player</code></li>
    </ul>

    <a class="btn" href="/player">Open Player</a>
  </body>
</html>
"""

PLAYER_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>roomba-player / player</title>
    <style>
      :root { --bg: #f7f8fa; --card: #fff; --border: #d7dbe1; --ink: #111; --accent: #1d6ef2; }
      body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: var(--bg); color: var(--ink); }
      .wrap { max-width: 1000px; margin: 0 auto; padding: 1rem; }
      .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
      .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; }
      .status { font-size: 0.95rem; margin: 0.3rem 0 0.8rem; }
      .btn { border: 1px solid #1f2937; background: #fff; color: #111; border-radius: 10px; padding: 0.5rem 0.8rem; cursor: pointer; }
      .btn:active, .btn.active { background: #1f2937; color: #fff; }
      .toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.8rem; }
      .joy { display: grid; grid-template-columns: 64px 64px 64px; grid-template-rows: 64px 64px 64px; gap: 0.4rem; justify-content: center; }
      .joy .btn { width: 64px; height: 64px; font-size: 1.2rem; padding: 0; }
      pre { background: #0f172a; color: #e5e7eb; border-radius: 10px; padding: 0.7rem; min-height: 110px; overflow: auto; }
      .small { font-size: 0.85rem; color: #374151; }
      #log { max-height: 240px; }
      kbd { border: 1px solid #999; border-bottom-width: 2px; border-radius: 6px; padding: 0.1rem 0.35rem; background: #fff; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Player</h1>
      <p class="small">Keyboard (AZERTY): <kbd>Z</kbd> forward, <kbd>S</kbd> backward, <kbd>Q</kbd> left, <kbd>D</kbd> right. Hold key/button to move, release to stop.</p>
      <div class="grid">
        <section class="card">
          <h2>Control</h2>
          <div class="status" id="ctrlStatus">control websocket: connecting...</div>
          <div class="toolbar">
            <button class="btn" id="btnInit">init</button>
            <button class="btn" id="btnSafe">mode safe</button>
            <button class="btn" id="btnFull">mode full</button>
            <button class="btn" id="btnClean">clean</button>
            <button class="btn" id="btnDock">dock</button>
            <button class="btn" id="btnStop">stop</button>
          </div>
          <div class="joy">
            <div></div>
            <button class="btn hold" data-cmd="forward">↑</button>
            <div></div>
            <button class="btn hold" data-cmd="left">←</button>
            <button class="btn" id="btnCenterStop">■</button>
            <button class="btn hold" data-cmd="right">→</button>
            <div></div>
            <button class="btn hold" data-cmd="backward">↓</button>
            <div></div>
          </div>
          <p class="small">Active command: <strong id="activeCmd">none</strong></p>
        </section>

        <section class="card">
          <h2>Telemetry</h2>
          <div class="status" id="telemetryStatus">telemetry websocket: connecting...</div>
          <pre id="telemetry">waiting...</pre>
        </section>

        <section class="card">
          <h2>Command log</h2>
          <pre id="log"></pre>
        </section>
      </div>
    </div>

    <script>
      const controlStatus = document.getElementById("ctrlStatus");
      const telemetryStatus = document.getElementById("telemetryStatus");
      const telemetryNode = document.getElementById("telemetry");
      const logNode = document.getElementById("log");
      const activeCmdNode = document.getElementById("activeCmd");

      let controlWs = null;
      let telemetryWs = null;
      let activeInput = null;

      function wsUrl(path) {
        const proto = window.location.protocol === "https:" ? "wss" : "ws";
        return `${proto}://${window.location.host}${path}`;
      }

      function addLog(line) {
        const ts = new Date().toLocaleTimeString();
        logNode.textContent = `[${ts}] ${line}\n` + logNode.textContent;
      }

      function setActive(name) {
        activeCmdNode.textContent = name || "none";
      }

      function sendControl(payload, source = "ui") {
        if (!controlWs || controlWs.readyState !== WebSocket.OPEN) {
          addLog(`control ws unavailable, drop: ${JSON.stringify(payload)}`);
          return;
        }
        controlWs.send(JSON.stringify(payload));
        addLog(`${source} -> ${JSON.stringify(payload)}`);
      }

      function commandPayload(cmd) {
        if (cmd === "forward") return { action: "drive", velocity: 180, radius: 1000 };
        if (cmd === "backward") return { action: "drive", velocity: -180, radius: 1000 };
        if (cmd === "left") return { action: "drive", velocity: 120, radius: 1 };
        if (cmd === "right") return { action: "drive", velocity: 120, radius: -1 };
        return { action: "stop" };
      }

      function startHold(cmd, source) {
        if (activeInput === cmd) return;
        activeInput = cmd;
        setActive(cmd);
        sendControl(commandPayload(cmd), source);
      }

      function stopHold(source) {
        if (!activeInput) return;
        activeInput = null;
        setActive("none");
        sendControl({ action: "stop" }, source);
      }

      function connectControl() {
        controlWs = new WebSocket(wsUrl("/ws/control"));
        controlWs.onopen = () => { controlStatus.textContent = "control websocket: connected"; };
        controlWs.onclose = () => {
          controlStatus.textContent = "control websocket: disconnected (retrying...)";
          setTimeout(connectControl, 1000);
        };
        controlWs.onerror = () => { controlStatus.textContent = "control websocket: error"; };
        controlWs.onmessage = (evt) => {
          addLog(`server <- ${evt.data}`);
        };
      }

      function connectTelemetry() {
        telemetryWs = new WebSocket(wsUrl("/ws/telemetry"));
        telemetryWs.onopen = () => { telemetryStatus.textContent = "telemetry websocket: connected"; };
        telemetryWs.onclose = () => {
          telemetryStatus.textContent = "telemetry websocket: disconnected (retrying...)";
          setTimeout(connectTelemetry, 1000);
        };
        telemetryWs.onerror = () => { telemetryStatus.textContent = "telemetry websocket: error"; };
        telemetryWs.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data);
            telemetryNode.textContent = JSON.stringify(data, null, 2);
          } catch (_) {
            telemetryNode.textContent = evt.data;
          }
        };
      }

      document.getElementById("btnInit").addEventListener("click", () => sendControl({ action: "init" }));
      document.getElementById("btnSafe").addEventListener("click", () => sendControl({ action: "mode", value: "safe" }));
      document.getElementById("btnFull").addEventListener("click", () => sendControl({ action: "mode", value: "full" }));
      document.getElementById("btnClean").addEventListener("click", () => sendControl({ action: "clean" }));
      document.getElementById("btnDock").addEventListener("click", () => sendControl({ action: "dock" }));
      document.getElementById("btnStop").addEventListener("click", () => stopHold("button"));
      document.getElementById("btnCenterStop").addEventListener("click", () => stopHold("button"));

      document.querySelectorAll(".hold").forEach((btn) => {
        const cmd = btn.getAttribute("data-cmd");
        const start = (ev) => {
          ev.preventDefault();
          document.querySelectorAll(".hold").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          startHold(cmd, "button-hold");
        };
        const stop = () => {
          btn.classList.remove("active");
          stopHold("button-release");
        };
        btn.addEventListener("mousedown", start);
        btn.addEventListener("mouseup", stop);
        btn.addEventListener("mouseleave", stop);
        btn.addEventListener("touchstart", start, { passive: false });
        btn.addEventListener("touchend", stop);
        btn.addEventListener("touchcancel", stop);
      });

      const keyMap = { z: "forward", s: "backward", q: "left", d: "right" };
      window.addEventListener("keydown", (ev) => {
        const key = ev.key.toLowerCase();
        if (!keyMap[key]) return;
        if (ev.repeat && activeInput === keyMap[key]) return;
        ev.preventDefault();
        startHold(keyMap[key], `keyboard:${key}:down`);
      });
      window.addEventListener("keyup", (ev) => {
        const key = ev.key.toLowerCase();
        if (!keyMap[key]) return;
        ev.preventDefault();
        stopHold(`keyboard:${key}:up`);
      });
      window.addEventListener("blur", () => stopHold("window-blur"));

      connectControl();
      connectTelemetry();
    </script>
  </body>
</html>
"""


@app.on_event("startup")
def startup() -> None:
    app.state.roomba = RoombaOI(
        port=settings.roomba_serial_port,
        baudrate=settings.roomba_baudrate,
        timeout=settings.roomba_timeout_sec,
    )


@app.on_event("shutdown")
def shutdown() -> None:
    app.state.roomba.close()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HOME_PAGE


@app.get("/player", response_class=HTMLResponse)
def player() -> str:
    return PLAYER_PAGE


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/telemetry")
def telemetry() -> dict:
    payload = get_telemetry_snapshot()
    payload["roomba_connected"] = app.state.roomba.connected
    return payload


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await telemetry_stream(websocket)


@app.websocket("/ws/control")
async def control_ws(websocket: WebSocket) -> None:
    await control_stream(websocket, app.state.roomba)
