"""FastAPI entrypoint."""

import json
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .camera import CameraService
from .config import settings
from .history import JsonlHistoryStore
from .odometry import OdometryEstimator
from .plan import PlanManager
from .roomba import RoombaOI
from .ws import control_stream, telemetry_stream

app = FastAPI(title="roomba-player", version="0.2.0")

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
      :root { --bg: #f3f6fb; --card: #ffffff; --border: #d4dcec; --ink: #0f172a; --muted: #475569; --accent: #1e40af; --ok: #15803d; --warn: #b45309; }
      body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: linear-gradient(180deg, #eef4ff 0%, #f8fbff 50%, #f3f6fb 100%); color: var(--ink); }
      .wrap { max-width: 1100px; margin: 0 auto; padding: 1rem; }
      .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
      .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 1rem; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05); }
      h1 { margin: 0.2rem 0 0.5rem; }
      h2 { margin: 0 0 0.7rem; font-size: 1.05rem; }
      .small { font-size: 0.9rem; color: var(--muted); }
      .toolbar { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-bottom: 0.8rem; }
      .btn { border: 1px solid #1f2937; background: #fff; color: #111; border-radius: 10px; padding: 0.5rem 0.8rem; cursor: pointer; transition: transform 80ms ease, background 120ms ease; }
      .btn:active { transform: translateY(1px); }
      .btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
      .joy { display: grid; grid-template-columns: 68px 68px 68px; grid-template-rows: 68px 68px 68px; gap: 0.45rem; justify-content: center; margin-top: 0.3rem; }
      .joy .btn { width: 68px; height: 68px; font-size: 1.2rem; padding: 0; }
      .status { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.6rem; }
      .camera-wrap { margin-bottom: 1rem; }
      .camera-box { border: 1px solid var(--border); border-radius: 14px; background: #0b1220; overflow: hidden; min-height: 120px; }
      .camera-box img { display: block; width: 100%; height: auto; max-height: 420px; object-fit: contain; background: #000; }
      .camera-off { color: #cbd5e1; padding: 0.9rem; }
      .speed { display: grid; grid-template-columns: 1fr auto; gap: 0.6rem; align-items: center; margin: 0.6rem 0 0.8rem; }
      input[type="range"] { width: 100%; }
      .telemetry { display: grid; grid-template-columns: repeat(2, minmax(120px, 1fr)); gap: 0.6rem; }
      .metric { border: 1px solid var(--border); border-radius: 10px; padding: 0.55rem; background: #fbfdff; }
      .metric .k { font-size: 0.78rem; color: var(--muted); }
      .metric .v { font-weight: 700; margin-top: 0.2rem; }
      .bar { height: 10px; border-radius: 999px; background: #e2e8f0; overflow: hidden; margin-top: 0.35rem; }
      .bar > span { display: block; height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); }
      .pill { display: inline-block; border-radius: 999px; padding: 0.15rem 0.45rem; font-size: 0.8rem; }
      .pill.ok { background: #dcfce7; color: var(--ok); }
      .pill.warn { background: #ffedd5; color: var(--warn); }
      pre { margin: 0; background: #0f172a; color: #e2e8f0; border-radius: 10px; padding: 0.7rem; max-height: 260px; overflow: auto; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Player</h1>
      <p class="small">Keyboard AZERTY: Z forward, S backward, Q left, D right. Hold to move, release to stop.</p>
      <section class="camera-wrap">
        <div class="camera-box" id="cameraBox">
          <div class="camera-off" id="cameraMessage">Camera stream disabled.</div>
          <img id="cameraFeed" alt="Raspberry camera stream" style="display:none;" />
        </div>
      </section>
      <section class="card">
        <h2>Salon Map</h2>
        <div class="toolbar">
          <button class="btn" id="btnLoadSalon">load plans/salon.yaml</button>
          <button class="btn" id="btnResetHistory">reset history + start pose</button>
          <input type="file" id="planFile" accept=".json,application/json" />
        </div>
        <p class="small">Odometry pose: <strong id="poseText">x=0 y=0 θ=0°</strong></p>
        <div style="position:relative;border:1px solid #d4dcec;border-radius:10px;background:#fff;overflow:hidden;">
          <canvas id="planStaticCanvas" width="900" height="380" style="display:block;width:100%;"></canvas>
          <canvas id="planRobotCanvas" width="900" height="380" style="position:absolute;inset:0;display:block;width:100%;pointer-events:none;"></canvas>
        </div>
      </section>

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

          <div class="speed">
            <input id="speedSlider" type="range" min="80" max="320" step="10" value="250" />
            <strong><span id="speedValue">250</span></strong>
          </div>

          <div class="joy">
            <div></div>
            <button class="btn hold" data-cmd="forward" id="joyForward">↑</button>
            <div></div>
            <button class="btn hold" data-cmd="left" id="joyLeft">←</button>
            <button class="btn" id="btnCenterStop">■</button>
            <button class="btn hold" data-cmd="right" id="joyRight">→</button>
            <div></div>
            <button class="btn hold" data-cmd="backward" id="joyBackward">↓</button>
            <div></div>
          </div>

          <p class="small">Active inputs: <strong id="activeInputs">none</strong></p>
          <p class="small">Executed command: <strong id="executedCommand">stop</strong></p>
        </section>

        <section class="card">
          <h2>Live Sensors</h2>
          <div class="status" id="telemetryStatus">telemetry websocket: connecting...</div>
          <div class="telemetry">
            <div class="metric">
              <div class="k">Battery</div>
              <div class="v"><span id="batteryPct">0</span>%</div>
              <div class="bar"><span id="batteryBar" style="width: 0%"></span></div>
            </div>
            <div class="metric">
              <div class="k">State</div>
              <div class="v" id="robotState">unknown</div>
            </div>
            <div class="metric">
              <div class="k">Bumpers</div>
              <div class="v" id="bumperState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Wheel drops</div>
              <div class="v" id="wheelDropState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Cliff sensors</div>
              <div class="v" id="cliffState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Charging source</div>
              <div class="v" id="chargingSourceState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Wall + dock</div>
              <div class="v" id="dockState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Roomba link</div>
              <div class="v" id="linkState"><span class="pill warn">unknown</span></div>
            </div>
            <div class="metric">
              <div class="k">Timestamp</div>
              <div class="v" id="telemetryTs">-</div>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>Realtime log</h2>
          <pre id="log"></pre>
        </section>
      </div>
    </div>

    <script>
      const controlStatus = document.getElementById("ctrlStatus");
      const telemetryStatus = document.getElementById("telemetryStatus");
      const logNode = document.getElementById("log");
      const speedSlider = document.getElementById("speedSlider");
      const speedValue = document.getElementById("speedValue");
      const cameraFeed = document.getElementById("cameraFeed");
      const cameraMessage = document.getElementById("cameraMessage");
      const activeInputsNode = document.getElementById("activeInputs");
      const executedCommandNode = document.getElementById("executedCommand");
      const CAMERA_ENABLED = __CAMERA_ENABLED__;
      const CAMERA_HTTP_PORT = __CAMERA_HTTP_PORT__;
      const CAMERA_HTTP_PATH = __CAMERA_HTTP_PATH__;

      const batteryPctNode = document.getElementById("batteryPct");
      const batteryBar = document.getElementById("batteryBar");
      const robotStateNode = document.getElementById("robotState");
      const bumperStateNode = document.getElementById("bumperState");
      const wheelDropStateNode = document.getElementById("wheelDropState");
      const cliffStateNode = document.getElementById("cliffState");
      const chargingSourceStateNode = document.getElementById("chargingSourceState");
      const dockStateNode = document.getElementById("dockState");
      const linkStateNode = document.getElementById("linkState");
      const telemetryTsNode = document.getElementById("telemetryTs");
      const planStaticCanvas = document.getElementById("planStaticCanvas");
      const planRobotCanvas = document.getElementById("planRobotCanvas");
      const poseTextNode = document.getElementById("poseText");
      const planFileInput = document.getElementById("planFile");

      let controlWs = null;
      let telemetryWs = null;
      const activeInputs = new Set();
      let lastCommandSignature = "";
      let currentPlan = null;
      let planProjection = null;
      let odomPollTimer = null;
      let currentOdom = { x_mm: 0, y_mm: 0, theta_deg: 0 };

      const buttonByCmd = {
        forward: document.getElementById("joyForward"),
        backward: document.getElementById("joyBackward"),
        left: document.getElementById("joyLeft"),
        right: document.getElementById("joyRight"),
      };

      function wsUrl(path) {
        const proto = window.location.protocol === "https:" ? "wss" : "ws";
        return `${proto}://${window.location.host}${path}`;
      }

      function addLog(line) {
        const ts = new Date().toLocaleTimeString();
        logNode.textContent = `[${ts}] ${line}\n` + logNode.textContent;
      }

      function sendControl(payload, source = "ui") {
        if (!controlWs || controlWs.readyState !== WebSocket.OPEN) {
          addLog(`control ws unavailable, drop: ${JSON.stringify(payload)}`);
          return;
        }
        controlWs.send(JSON.stringify(payload));
        addLog(`${source} -> ${JSON.stringify(payload)}`);
      }

      function currentSpeed() {
        return Number(speedSlider.value || 250);
      }

      async function startCameraIfEnabled() {
        if (!CAMERA_ENABLED) {
          cameraMessage.textContent = "Camera stream disabled.";
          return;
        }
        const baseUrl = `/camera/stream`;
        let retryTimer = null;
        const ensureStarted = async () => {
          try {
            const r = await fetch("/camera/start", { method: "POST" });
            const j = await r.json();
            addLog(`camera/start -> ${JSON.stringify(j)}`);
          } catch (_) {
            addLog("camera start request failed");
          }
        };
        const scheduleRetry = () => {
          if (retryTimer) return;
          retryTimer = setTimeout(() => {
            retryTimer = null;
            ensureStarted().finally(() => {
              const sep = baseUrl.includes("?") ? "&" : "?";
              cameraFeed.src = `${baseUrl}${sep}t=${Date.now()}`;
            });
          }, 1200);
        };
        await ensureStarted();
        cameraMessage.textContent = "Camera stream loading...";
        cameraFeed.src = `${baseUrl}?t=${Date.now()}`;
        cameraFeed.style.display = "block";
        cameraFeed.onload = () => {
          cameraMessage.style.display = "none";
        };
        cameraFeed.onerror = () => {
          cameraMessage.style.display = "block";
          cameraMessage.textContent = "Camera stream unavailable (retrying...)";
          scheduleRetry();
        };
      }

      function listActiveInputs() {
        return Array.from(activeInputs).sort();
      }

      function setActiveButtonStyles() {
        for (const [cmd, btn] of Object.entries(buttonByCmd)) {
          if (activeInputs.has(cmd)) {
            btn.classList.add("active");
          } else {
            btn.classList.remove("active");
          }
        }
      }

      function computeDrivePayload() {
        const speed = currentSpeed();
        const hasF = activeInputs.has("forward");
        const hasB = activeInputs.has("backward");
        const hasL = activeInputs.has("left");
        const hasR = activeInputs.has("right");

        let velocity = 0;
        if (hasF && !hasB) velocity = speed;
        if (hasB && !hasF) velocity = -speed;

        let radius = 32768;
        if (hasL && !hasR) {
          radius = velocity === 0 ? 1 : 220;
          if (velocity === 0) velocity = speed;
        }
        if (hasR && !hasL) {
          radius = velocity === 0 ? -1 : -220;
          if (velocity === 0) velocity = speed;
        }

        if (velocity === 0 && (!hasL || !hasR)) {
          return { action: "stop" };
        }
        return { action: "drive", velocity, radius };
      }

      function applyDriveFromInputs(source) {
        const inputs = listActiveInputs();
        activeInputsNode.textContent = inputs.length ? inputs.join(" + ") : "none";
        setActiveButtonStyles();

        const payload = computeDrivePayload();
        const signature = JSON.stringify(payload);
        if (signature === lastCommandSignature) return;
        lastCommandSignature = signature;

        if (payload.action === "stop") {
          executedCommandNode.textContent = "stop";
        } else {
          executedCommandNode.textContent = `drive v=${payload.velocity} r=${payload.radius}`;
        }
        sendControl(payload, source);
      }

      function startInput(cmd, source) {
        activeInputs.add(cmd);
        applyDriveFromInputs(source);
      }

      function stopInput(cmd, source) {
        activeInputs.delete(cmd);
        applyDriveFromInputs(source);
      }

      function setPill(node, ok) {
        node.innerHTML = ok
          ? '<span class="pill ok">yes</span>'
          : '<span class="pill warn">no</span>';
      }

      function setTextPill(node, text, ok = true) {
        node.innerHTML = ok
          ? `<span class="pill ok">${text}</span>`
          : `<span class="pill warn">${text}</span>`;
      }

      function rotatePoint(x, y, theta) {
        const c = Math.cos(theta);
        const s = Math.sin(theta);
        return [x * c - y * s, x * s + y * c];
      }

      function computePlanBounds(plan) {
        const pts = [...(plan.contour || [])];
        const shapes = plan.object_shapes || {};
        for (const obj of plan.objects || []) {
          const shape = shapes[obj.shape_ref];
          if (!shape || !Array.isArray(shape.contour)) continue;
          const theta = ((obj.theta_deg || 0) * Math.PI) / 180;
          for (const p of shape.contour) {
            const [rx, ry] = rotatePoint(p[0], p[1], theta);
            pts.push([rx + (obj.x_mm || 0), ry + (obj.y_mm || 0)]);
          }
        }
        const xs = pts.map((p) => p[0]);
        const ys = pts.map((p) => p[1]);
        return {
          minX: Math.min(...xs),
          maxX: Math.max(...xs),
          minY: Math.min(...ys),
          maxY: Math.max(...ys),
        };
      }

      function drawPolygon(ctx, points, tx, ty, scale, stroke, fill = null) {
        if (!points || points.length < 2) return;
        ctx.beginPath();
        const p0 = points[0];
        ctx.moveTo(tx(p0[0], scale), ty(p0[1], scale));
        for (let i = 1; i < points.length; i += 1) {
          const p = points[i];
          ctx.lineTo(tx(p[0], scale), ty(p[1], scale));
        }
        ctx.closePath();
        if (fill) {
          ctx.fillStyle = fill;
          ctx.fill();
        }
        ctx.strokeStyle = stroke;
        ctx.stroke();
      }

      async function refreshPlan() {
        try {
          const r = await fetch("/api/plan");
          const j = await r.json();
          currentPlan = j.plan || null;
        } catch (_) {
          currentPlan = null;
        }
        renderStaticPlan();
        drawRobotPose();
      }

      function renderStaticPlan() {
        const ctx = planStaticCanvas.getContext("2d");
        ctx.clearRect(0, 0, planStaticCanvas.width, planStaticCanvas.height);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, planStaticCanvas.width, planStaticCanvas.height);
        planProjection = null;
        if (!currentPlan) return;

        const b = computePlanBounds(currentPlan);
        const pad = 20;
        const sx = (planStaticCanvas.width - pad * 2) / Math.max(1, b.maxX - b.minX);
        const sy = (planStaticCanvas.height - pad * 2) / Math.max(1, b.maxY - b.minY);
        const scale = Math.min(sx, sy);
        const height = planStaticCanvas.height;
        const tx = (x, s) => pad + (x - b.minX) * s;
        const ty = (y, s) => height - pad - (y - b.minY) * s;
        planProjection = { minX: b.minX, minY: b.minY, pad, scale, height };

        ctx.lineWidth = 2;
        drawPolygon(ctx, currentPlan.contour, tx, ty, scale, "#334155", "#f8fafc");

        const shapes = currentPlan.object_shapes || {};
        for (const obj of currentPlan.objects || []) {
          const shape = shapes[obj.shape_ref];
          if (!shape) continue;
          const theta = ((obj.theta_deg || 0) * Math.PI) / 180;
          const pts = (shape.contour || []).map((p) => {
            const [rx, ry] = rotatePoint(p[0], p[1], theta);
            return [rx + (obj.x_mm || 0), ry + (obj.y_mm || 0)];
          });
          drawPolygon(ctx, pts, tx, ty, scale, "#94a3b8", "#e2e8f0");
        }
      }

      function projectX(x) {
        return planProjection.pad + (x - planProjection.minX) * planProjection.scale;
      }

      function projectY(y) {
        return planProjection.height - planProjection.pad - (y - planProjection.minY) * planProjection.scale;
      }

      function drawRobotPose() {
        const ctx = planRobotCanvas.getContext("2d");
        ctx.clearRect(0, 0, planRobotCanvas.width, planRobotCanvas.height);
        poseTextNode.textContent = `x=${Math.round(currentOdom.x_mm || 0)} y=${Math.round(currentOdom.y_mm || 0)} θ=${Math.round(currentOdom.theta_deg || 0)}°`;
        if (!planProjection) return;

        const rx = projectX(currentOdom.x_mm || 0);
        const ry = projectY(currentOdom.y_mm || 0);
        const theta = ((currentOdom.theta_deg || 0) * Math.PI) / 180;
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(rx, ry, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ef4444";
        ctx.beginPath();
        ctx.moveTo(rx, ry);
        ctx.lineTo(rx + 18 * Math.cos(theta), ry - 18 * Math.sin(theta));
        ctx.stroke();
      }

      async function refreshOdometry() {
        try {
          const r = await fetch("/api/odometry");
          currentOdom = await r.json();
        } catch (_) {}
        drawRobotPose();
      }

      function startOdometryPolling() {
        if (odomPollTimer) clearInterval(odomPollTimer);
        refreshOdometry();
        odomPollTimer = setInterval(refreshOdometry, 120);
      }

      function connectControl() {
        controlWs = new WebSocket(wsUrl("/ws/control"));
        controlWs.onopen = () => { controlStatus.textContent = "control websocket: connected"; };
        controlWs.onclose = () => {
          controlStatus.textContent = "control websocket: disconnected (retrying...)";
          setTimeout(connectControl, 1000);
        };
        controlWs.onerror = () => { controlStatus.textContent = "control websocket: error"; };
        controlWs.onmessage = (evt) => addLog(`server <- ${evt.data}`);
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
            const battery = Number(data.battery_pct || 0);
            batteryPctNode.textContent = String(battery);
            batteryBar.style.width = `${Math.max(0, Math.min(100, battery))}%`;
            const chargingState = String(data.state || "unknown");
            const chargingCode = String(data.charging_state_code ?? "?");
            robotStateNode.textContent = `${chargingState} (code ${chargingCode})`;

            const bumpLeft = Boolean(data.bump_left);
            const bumpRight = Boolean(data.bump_right);
            setTextPill(
              bumperStateNode,
              `L:${bumpLeft ? "1" : "0"} R:${bumpRight ? "1" : "0"}`,
              bumpLeft || bumpRight
            );

            const wdLeft = Boolean(data.wheel_drop_left);
            const wdRight = Boolean(data.wheel_drop_right);
            const wdCaster = Boolean(data.wheel_drop_caster);
            setTextPill(
              wheelDropStateNode,
              `L:${wdLeft ? "1" : "0"} R:${wdRight ? "1" : "0"} C:${wdCaster ? "1" : "0"}`,
              wdLeft || wdRight || wdCaster
            );

            const cliffL = Boolean(data.cliff_left);
            const cliffFL = Boolean(data.cliff_front_left);
            const cliffFR = Boolean(data.cliff_front_right);
            const cliffR = Boolean(data.cliff_right);
            setTextPill(
              cliffStateNode,
              `L:${cliffL ? "1" : "0"} FL:${cliffFL ? "1" : "0"} FR:${cliffFR ? "1" : "0"} R:${cliffR ? "1" : "0"}`,
              cliffL || cliffFL || cliffFR || cliffR
            );

            const sourceHome = Boolean(data.charging_source_home_base);
            const sourceInternal = Boolean(data.charging_source_internal);
            const srcText = `${sourceHome ? "home_base " : ""}${sourceInternal ? "internal " : ""}`.trim() || "none";
            setTextPill(chargingSourceStateNode, srcText, sourceHome || sourceInternal);

            const wallSeen = Boolean(data.wall_seen);
            const dockVisible = Boolean(data.dock_visible);
            setTextPill(dockStateNode, `wall:${wallSeen ? "1" : "0"} dock:${dockVisible ? "1" : "0"}`, wallSeen || dockVisible);
            setPill(linkStateNode, Boolean(data.roomba_connected));
            telemetryTsNode.textContent = String(data.timestamp || "-");
            if (data.odometry) {
              currentOdom = data.odometry;
              drawRobotPose();
            }
          } catch (_) {
            addLog(`telemetry parse error: ${evt.data}`);
          }
        };
      }

      document.getElementById("btnInit").addEventListener("click", () => sendControl({ action: "init" }));
      document.getElementById("btnSafe").addEventListener("click", () => sendControl({ action: "mode", value: "safe" }));
      document.getElementById("btnFull").addEventListener("click", () => sendControl({ action: "mode", value: "full" }));
      document.getElementById("btnClean").addEventListener("click", () => sendControl({ action: "clean" }));
      document.getElementById("btnDock").addEventListener("click", () => sendControl({ action: "dock" }));
      document.getElementById("btnStop").addEventListener("click", () => {
        activeInputs.clear();
        applyDriveFromInputs("button-stop");
      });
      document.getElementById("btnLoadSalon").addEventListener("click", async () => {
        try {
          const r = await fetch("/api/plan/load-file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: "plans/salon.yaml" }),
          });
          const j = await r.json();
          addLog(`plan/load-file -> ${JSON.stringify(j)}`);
          await refreshPlan();
        } catch (_) {
          addLog("plan/load-file failed");
        }
      });
      document.getElementById("btnResetHistory").addEventListener("click", async () => {
        try {
          const r = await fetch("/api/odometry/reset-history", { method: "POST" });
          const j = await r.json();
          addLog(`odometry/reset-history -> ${JSON.stringify(j)}`);
          await refreshOdometry();
        } catch (_) {
          addLog("odometry/reset-history failed");
        }
      });
      planFileInput.addEventListener("change", async (ev) => {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const plan = JSON.parse(text);
          const r = await fetch("/api/plan/load-json", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(plan),
          });
          const j = await r.json();
          addLog(`plan/load-json -> ${JSON.stringify(j)}`);
          await refreshPlan();
        } catch (_) {
          addLog("plan/load-json failed");
        }
      });
      document.getElementById("btnCenterStop").addEventListener("click", () => {
        activeInputs.clear();
        applyDriveFromInputs("button-stop-center");
      });

      speedSlider.addEventListener("input", () => {
        speedValue.textContent = speedSlider.value;
        if (activeInputs.size > 0) applyDriveFromInputs("speed-slider");
      });

      document.querySelectorAll(".hold").forEach((btn) => {
        const cmd = btn.getAttribute("data-cmd");
        const start = (ev) => {
          ev.preventDefault();
          startInput(cmd, `button:${cmd}:down`);
        };
        const stop = (ev) => {
          if (ev) ev.preventDefault();
          stopInput(cmd, `button:${cmd}:up`);
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
        const cmd = keyMap[key];
        if (!cmd) return;
        ev.preventDefault();
        startInput(cmd, `keyboard:${key}:down`);
      });
      window.addEventListener("keyup", (ev) => {
        const key = ev.key.toLowerCase();
        const cmd = keyMap[key];
        if (!cmd) return;
        ev.preventDefault();
        stopInput(cmd, `keyboard:${key}:up`);
      });
      window.addEventListener("blur", () => {
        activeInputs.clear();
        applyDriveFromInputs("window-blur");
      });

      speedValue.textContent = speedSlider.value;
      startCameraIfEnabled();
      connectControl();
      connectTelemetry();
      refreshPlan();
      startOdometryPolling();
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
    app.state.odometry_history = JsonlHistoryStore(settings.odometry_history_path)
    app.state.odometry = OdometryEstimator(
        history_sink=app.state.odometry_history.append,
        source=settings.odometry_source,
        linear_scale=settings.odometry_linear_scale,
        angular_scale=settings.odometry_angular_scale,
    )
    app.state.plan = PlanManager()
    app.state.camera = CameraService(
        enabled=settings.camera_stream_enabled,
        width=settings.camera_width,
        height=settings.camera_height,
        framerate=settings.camera_framerate,
        profile=settings.camera_profile,
        shutter=settings.camera_shutter,
        denoise=settings.camera_denoise,
        sharpness=settings.camera_sharpness,
        awb=settings.camera_awb,
        h264_tcp_port=settings.camera_h264_tcp_port,
        http_bind_host=settings.camera_http_bind_host,
        http_port=settings.camera_http_port,
        http_path=settings.camera_http_path,
    )
    restored_pose = app.state.odometry_history.last_pose()
    if restored_pose:
        app.state.odometry.reset(
            x_mm=restored_pose.get("x_mm", 0),
            y_mm=restored_pose.get("y_mm", 0),
            theta_deg=restored_pose.get("theta_deg", 0),
        )

    if settings.plan_default_path:
        try:
            loaded = app.state.plan.load_from_file(settings.plan_default_path)
            if not restored_pose:
                start_pose = (loaded or {}).get("start_pose") or {}
                telemetry = app.state.roomba.get_telemetry_snapshot()
                app.state.odometry.reset(
                    x_mm=start_pose.get("x_mm", 0),
                    y_mm=start_pose.get("y_mm", 0),
                    theta_deg=start_pose.get("theta_deg", 0),
                    base_total_distance_mm=telemetry.get("total_distance_mm"),
                    base_total_angle_deg=telemetry.get("total_angle_deg"),
                    base_left_encoder_counts=telemetry.get("left_encoder_counts"),
                    base_right_encoder_counts=telemetry.get("right_encoder_counts"),
                )
        except Exception:
            pass


@app.on_event("shutdown")
def shutdown() -> None:
    app.state.roomba.close()
    app.state.camera.stop()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HOME_PAGE


@app.get("/player", response_class=HTMLResponse)
def player() -> str:
    app.state.camera.start_if_enabled()
    return (
        PLAYER_PAGE.replace("__CAMERA_ENABLED__", json.dumps(settings.camera_stream_enabled))
        .replace("__CAMERA_HTTP_PORT__", json.dumps(settings.camera_http_port))
        .replace("__CAMERA_HTTP_PATH__", json.dumps(settings.camera_http_path))
    )


@app.post("/camera/start")
def camera_start() -> dict:
    return app.state.camera.start_if_enabled()


@app.get("/camera/stream")
def camera_stream():
    start = app.state.camera.start_if_enabled()
    if not start.get("enabled"):
        return JSONResponse({"ok": False, "error": "camera_disabled"}, status_code=404)
    if not start.get("started"):
        return JSONResponse({"ok": False, "error": start.get("reason", "camera_not_ready")}, status_code=503)
    try:
        camera_proc, ffmpeg_proc = app.state.camera.open_stream_processes()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"camera_pipeline_error:{exc}"}, status_code=503)

    def stream_iter():
        try:
            while True:
                chunk = ffmpeg_proc.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            app.state.camera.stop()

    return StreamingResponse(stream_iter(), media_type="multipart/x-mixed-replace; boundary=ffmpeg")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


def _plan_start_pose() -> dict:
    plan = app.state.plan.get() or {}
    start_pose = plan.get("start_pose") or {}
    return {
        "x_mm": start_pose.get("x_mm", 0),
        "y_mm": start_pose.get("y_mm", 0),
        "theta_deg": start_pose.get("theta_deg", 0),
    }


@app.get("/api/plan")
def get_plan() -> dict:
    return {"plan": app.state.plan.get()}


@app.post("/api/plan/load-file")
def load_plan_file(payload: dict) -> dict:
    path = str(payload.get("path", "")).strip()
    if not path:
        return {"ok": False, "error": "missing_path"}
    try:
        plan = app.state.plan.load_from_file(path)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    start_pose = (plan or {}).get("start_pose") or {}
    telemetry = app.state.roomba.get_telemetry_snapshot()
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
        base_total_distance_mm=telemetry.get("total_distance_mm"),
        base_total_angle_deg=telemetry.get("total_angle_deg"),
        base_left_encoder_counts=telemetry.get("left_encoder_counts"),
        base_right_encoder_counts=telemetry.get("right_encoder_counts"),
    )
    return {"ok": True}


@app.post("/api/plan/load-json")
def load_plan_json(payload: dict) -> dict:
    try:
        plan = app.state.plan.load_from_json(payload)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    start_pose = (plan or {}).get("start_pose") or {}
    telemetry = app.state.roomba.get_telemetry_snapshot()
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
        base_total_distance_mm=telemetry.get("total_distance_mm"),
        base_total_angle_deg=telemetry.get("total_angle_deg"),
        base_left_encoder_counts=telemetry.get("left_encoder_counts"),
        base_right_encoder_counts=telemetry.get("right_encoder_counts"),
    )
    return {"ok": True}


@app.get("/api/odometry")
def get_odometry() -> dict:
    app.state.odometry.update_from_telemetry(app.state.roomba.get_telemetry_snapshot())
    return app.state.odometry.get_pose()


@app.post("/api/odometry/reset")
def reset_odometry(payload: dict | None = None) -> dict:
    data = payload or {}
    telemetry = app.state.roomba.get_telemetry_snapshot()
    app.state.odometry.reset(
        x_mm=data.get("x_mm", 0),
        y_mm=data.get("y_mm", 0),
        theta_deg=data.get("theta_deg", 0),
        base_total_distance_mm=telemetry.get("total_distance_mm"),
        base_total_angle_deg=telemetry.get("total_angle_deg"),
        base_left_encoder_counts=telemetry.get("left_encoder_counts"),
        base_right_encoder_counts=telemetry.get("right_encoder_counts"),
    )
    return {"ok": True, **app.state.odometry.get_pose()}


@app.post("/api/odometry/reset-history")
def reset_odometry_history() -> dict:
    app.state.odometry_history.clear()
    telemetry = app.state.roomba.get_telemetry_snapshot()
    start_pose = _plan_start_pose()
    app.state.odometry.reset(
        x_mm=start_pose.get("x_mm", 0),
        y_mm=start_pose.get("y_mm", 0),
        theta_deg=start_pose.get("theta_deg", 0),
        base_total_distance_mm=telemetry.get("total_distance_mm"),
        base_total_angle_deg=telemetry.get("total_angle_deg"),
        base_left_encoder_counts=telemetry.get("left_encoder_counts"),
        base_right_encoder_counts=telemetry.get("right_encoder_counts"),
    )
    return {"ok": True, "history_cleared": True, **app.state.odometry.get_pose()}


@app.get("/telemetry")
def telemetry() -> dict:
    payload = app.state.roomba.get_telemetry_snapshot()
    payload["odometry"] = app.state.odometry.update_from_telemetry(payload)
    return payload


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await telemetry_stream(websocket, app.state.roomba, app.state.odometry)


@app.websocket("/ws/control")
async def control_ws(websocket: WebSocket) -> None:
    await control_stream(websocket, app.state.roomba, app.state.odometry)
