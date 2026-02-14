(function () {
  const RP = window.RP;

  async function bindPlanActions() {
    document.getElementById("btnLoadSalon").addEventListener("click", async () => {
      try {
        const r = await fetch("/api/plan/load-file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: "plans/salon.yaml" }),
        });
        const j = await r.json();
        RP.utils.addLog(`plan/load-file -> ${JSON.stringify(j)}`);
        await RP.map.refreshPlan();
      } catch (_) {
        RP.utils.addLog("plan/load-file failed");
      }
    });

    document.getElementById("btnResetHistory").addEventListener("click", async () => {
      try {
        const r = await fetch("/api/odometry/reset-history", { method: "POST" });
        const j = await r.json();
        RP.utils.addLog(`odometry/reset-history -> ${JSON.stringify(j)}`);
        if (j && typeof j.x_mm === "number") {
          RP.state.currentOdom = j;
          RP.map.drawRobotPose();
        }
      } catch (_) {
        RP.utils.addLog("odometry/reset-history failed");
      }
    });

    RP.refs.planFileInput.addEventListener("change", async (ev) => {
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
        RP.utils.addLog(`plan/load-json -> ${JSON.stringify(j)}`);
        await RP.map.refreshPlan();
      } catch (_) {
        RP.utils.addLog("plan/load-json failed");
      }
    });
  }

  function start() {
    RP.refs.speedValue.textContent = RP.refs.speedSlider.value;
    RP.camera.startCameraIfEnabled();
    RP.aruco.startArucoIfEnabled();
    RP.controls.connectControl();
    RP.controls.bindControls();
    RP.telemetry.connectTelemetry();
    bindPlanActions();
    RP.map.refreshPlan();
  }

  start();
})();
