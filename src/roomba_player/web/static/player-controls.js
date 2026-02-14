(function () {
  const RP = window.RP;

  const buttonByCmd = {
    forward: document.getElementById("joyForward"),
    backward: document.getElementById("joyBackward"),
    left: document.getElementById("joyLeft"),
    right: document.getElementById("joyRight"),
  };

  function sendControl(payload, source) {
    const ws = RP.state.controlWs;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      RP.utils.addLog(`control ws unavailable, drop: ${JSON.stringify(payload)}`);
      return;
    }
    ws.send(JSON.stringify(payload));
    RP.utils.addLog(`${source} -> ${JSON.stringify(payload)}`);
  }

  function currentSpeed() {
    return Number(RP.refs.speedSlider.value || 250);
  }

  function listActiveInputs() {
    return Array.from(RP.state.activeInputs).sort();
  }

  function setActiveButtonStyles() {
    for (const entry of Object.entries(buttonByCmd)) {
      const cmd = entry[0];
      const btn = entry[1];
      if (RP.state.activeInputs.has(cmd)) btn.classList.add("active");
      else btn.classList.remove("active");
    }
  }

  function computeDrivePayload() {
    const speed = currentSpeed();
    const hasF = RP.state.activeInputs.has("forward");
    const hasB = RP.state.activeInputs.has("backward");
    const hasL = RP.state.activeInputs.has("left");
    const hasR = RP.state.activeInputs.has("right");

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

    if (velocity === 0 && (!hasL || !hasR)) return { action: "stop" };
    return applyBumperGuard({ action: "drive", velocity, radius });
  }

  function applyBumperGuard(payload) {
    if (payload.action !== "drive") return payload;
    const bumpLeft = RP.state.bumpLeft;
    const bumpRight = RP.state.bumpRight;
    const v = Number(payload.velocity || 0);
    const r = Number(payload.radius || 32768);
    if (bumpLeft && bumpRight) return v < 0 ? payload : { action: "stop" };

    if (bumpLeft) {
      if (v < 0) return payload;
      if (r < 0) return payload; // only turn right
      return { action: "stop" };
    }

    if (bumpRight) {
      if (v < 0) return payload;
      if (r > 0) return payload; // only turn left
      return { action: "stop" };
    }

    return payload;
  }

  function applyDriveFromInputs(source) {
    const inputs = listActiveInputs();
    RP.refs.activeInputsNode.textContent = inputs.length ? inputs.join(" + ") : "none";
    setActiveButtonStyles();

    const payload = computeDrivePayload();
    const signature = JSON.stringify(payload);
    if (signature === RP.state.lastCommandSignature) return;
    RP.state.lastCommandSignature = signature;

    if (payload.action === "stop") RP.refs.executedCommandNode.textContent = "stop";
    else RP.refs.executedCommandNode.textContent = `drive v=${payload.velocity} r=${payload.radius}`;
    sendControl(payload, source);
  }

  function startInput(cmd, source) {
    RP.state.activeInputs.add(cmd);
    applyDriveFromInputs(source);
  }

  function stopInput(cmd, source) {
    RP.state.activeInputs.delete(cmd);
    applyDriveFromInputs(source);
  }

  function connectControl() {
    RP.state.controlWs = new WebSocket(RP.utils.wsUrl("/ws/control"));
    RP.state.controlWs.onopen = () => { RP.refs.controlStatus.textContent = "control websocket: connected"; };
    RP.state.controlWs.onclose = () => {
      RP.refs.controlStatus.textContent = "control websocket: disconnected (retrying...)";
      setTimeout(connectControl, 1000);
    };
    RP.state.controlWs.onerror = () => { RP.refs.controlStatus.textContent = "control websocket: error"; };
    RP.state.controlWs.onmessage = (evt) => RP.utils.addLog(`server <- ${evt.data}`);
  }

  function bindControls() {
    document.getElementById("btnInit").addEventListener("click", () => sendControl({ action: "init" }, "ui"));
    document.getElementById("btnSafe").addEventListener("click", () => sendControl({ action: "mode", value: "safe" }, "ui"));
    document.getElementById("btnFull").addEventListener("click", () => sendControl({ action: "mode", value: "full" }, "ui"));
    document.getElementById("btnClean").addEventListener("click", () => sendControl({ action: "clean" }, "ui"));
    document.getElementById("btnDock").addEventListener("click", () => sendControl({ action: "dock" }, "ui"));

    document.getElementById("btnStop").addEventListener("click", () => {
      RP.state.activeInputs.clear();
      applyDriveFromInputs("button-stop");
    });

    document.getElementById("btnCenterStop").addEventListener("click", () => {
      RP.state.activeInputs.clear();
      applyDriveFromInputs("button-stop-center");
    });

    RP.refs.speedSlider.addEventListener("input", () => {
      RP.refs.speedValue.textContent = RP.refs.speedSlider.value;
      if (RP.state.activeInputs.size > 0) applyDriveFromInputs("speed-slider");
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
      RP.state.activeInputs.clear();
      applyDriveFromInputs("window-blur");
    });
  }

  RP.controls = { connectControl, bindControls };
})();
