(function () {
  const RP = window.RP;

  function connectTelemetry() {
    RP.state.telemetryWs = new WebSocket(RP.utils.wsUrl("/ws/telemetry"));
    RP.state.telemetryWs.onopen = () => { RP.refs.telemetryStatus.textContent = "telemetry websocket: connected"; };
    RP.state.telemetryWs.onclose = () => {
      RP.refs.telemetryStatus.textContent = "telemetry websocket: disconnected (retrying...)";
      setTimeout(connectTelemetry, 1000);
    };
    RP.state.telemetryWs.onerror = () => { RP.refs.telemetryStatus.textContent = "telemetry websocket: error"; };
    RP.state.telemetryWs.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        const battery = Number(data.battery_pct || 0);
        RP.refs.batteryPctNode.textContent = String(battery);
        RP.refs.batteryBar.style.width = `${Math.max(0, Math.min(100, battery))}%`;
        const chargingState = String(data.state || "unknown");
        const chargingCode = String(data.charging_state_code ?? "?");
        RP.refs.robotStateNode.textContent = `${chargingState} (code ${chargingCode})`;

        const bumpLeft = Boolean(data.bump_left);
        const bumpRight = Boolean(data.bump_right);
        RP.state.bumpLeft = bumpLeft;
        RP.state.bumpRight = bumpRight;
        RP.utils.setTextPill(RP.refs.bumperStateNode, `L:${bumpLeft ? "1" : "0"} R:${bumpRight ? "1" : "0"}`, bumpLeft || bumpRight);

        const wdLeft = Boolean(data.wheel_drop_left);
        const wdRight = Boolean(data.wheel_drop_right);
        const wdCaster = Boolean(data.wheel_drop_caster);
        RP.utils.setTextPill(RP.refs.wheelDropStateNode, `L:${wdLeft ? "1" : "0"} R:${wdRight ? "1" : "0"} C:${wdCaster ? "1" : "0"}`, wdLeft || wdRight || wdCaster);

        const cliffL = Boolean(data.cliff_left);
        const cliffFL = Boolean(data.cliff_front_left);
        const cliffFR = Boolean(data.cliff_front_right);
        const cliffR = Boolean(data.cliff_right);
        RP.utils.setTextPill(RP.refs.cliffStateNode, `L:${cliffL ? "1" : "0"} FL:${cliffFL ? "1" : "0"} FR:${cliffFR ? "1" : "0"} R:${cliffR ? "1" : "0"}`, cliffL || cliffFL || cliffFR || cliffR);

        const sourceHome = Boolean(data.charging_source_home_base);
        const sourceInternal = Boolean(data.charging_source_internal);
        const srcText = `${sourceHome ? "home_base " : ""}${sourceInternal ? "internal " : ""}`.trim() || "none";
        RP.utils.setTextPill(RP.refs.chargingSourceStateNode, srcText, sourceHome || sourceInternal);

        const wallSeen = Boolean(data.wall_seen);
        const dockVisible = Boolean(data.dock_visible);
        RP.utils.setTextPill(RP.refs.dockStateNode, `wall:${wallSeen ? "1" : "0"} dock:${dockVisible ? "1" : "0"}`, wallSeen || dockVisible);
        RP.utils.setPill(RP.refs.linkStateNode, Boolean(data.roomba_connected));
        RP.refs.telemetryTsNode.textContent = String(data.timestamp || "-");

        if (data.odometry) {
          RP.state.currentOdom = data.odometry;
          RP.map.drawRobotPose();
        }
        if (RP.aruco && typeof RP.aruco.updateFromTelemetry === "function") {
          RP.aruco.updateFromTelemetry(data.aruco || null);
        }
      } catch (_) {
        RP.utils.addLog(`telemetry parse error: ${evt.data}`);
      }
    };
  }

  RP.telemetry = { connectTelemetry };
})();
