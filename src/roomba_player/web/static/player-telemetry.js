(function () {
  const RP = window.RP;

  function normalizeAngleDeg(angle) {
    let a = Number(angle || 0);
    while (a > 180) a -= 360;
    while (a < -180) a += 360;
    return a;
  }

  function markerAxis(markerCfg) {
    const mx = Number(markerCfg && markerCfg.x_mm);
    const my = Number(markerCfg && markerCfg.y_mm);
    if (!Number.isFinite(mx) || !Number.isFinite(my)) return null;
    const snap = markerCfg && markerCfg.snap_pose;
    if (snap && Number.isFinite(Number(snap.x_mm)) && Number.isFinite(Number(snap.y_mm))) {
      const vx = Number(snap.x_mm) - mx;
      const vy = Number(snap.y_mm) - my;
      const n = Math.hypot(vx, vy);
      if (n > 1e-6) return { x: vx / n, y: vy / n };
    }
    const theta = (Number(markerCfg && markerCfg.theta_deg) * Math.PI) / 180;
    return { x: Math.cos(theta), y: Math.sin(theta) };
  }

  function computeArucoPairEstimate(aruco) {
    if (!aruco || !aruco.ok) return null;
    const plan = RP.state.currentPlan;
    if (!plan || !Array.isArray(plan.aruco_markers)) return null;
    const detections = Array.isArray(aruco.markers) ? aruco.markers.filter((m) => m && Number.isFinite(Number(m.id))) : [];
    if (detections.length < 2) return null;

    const cfgById = new Map();
    for (const cfg of plan.aruco_markers) {
      const id = Number(cfg && cfg.id);
      if (Number.isFinite(id)) cfgById.set(id, cfg);
    }

    let best = null;
    for (let i = 0; i < detections.length; i += 1) {
      const da = detections[i];
      const cfgA = cfgById.get(Number(da.id));
      if (!cfgA) continue;
      for (let j = i + 1; j < detections.length; j += 1) {
        const db = detections[j];
        const cfgB = cfgById.get(Number(db.id));
        if (!cfgB) continue;
        const ax = Number(cfgA.x_mm || 0);
        const ay = Number(cfgA.y_mm || 0);
        const bx = Number(cfgB.x_mm || 0);
        const by = Number(cfgB.y_mm || 0);
        const worldDist = Math.hypot(bx - ax, by - ay);
        if (worldDist < 80) continue;
        const ac = Array.isArray(da.center) ? da.center : [0, 0];
        const bc = Array.isArray(db.center) ? db.center : [0, 0];
        const pixelDist = Math.hypot(Number(bc[0] || 0) - Number(ac[0] || 0), Number(bc[1] || 0) - Number(ac[1] || 0));
        if (pixelDist < 2) continue;
        const areaSum = Number(da.area_px || 0) + Number(db.area_px || 0);
        const score = areaSum + (120 * pixelDist);
        if (!best || score > best.score) {
          best = { score, da, db, cfgA, cfgB, worldDist, pixelDist };
        }
      }
    }
    if (!best) return null;

    const ax = Number(best.cfgA.x_mm || 0);
    const ay = Number(best.cfgA.y_mm || 0);
    const bx = Number(best.cfgB.x_mm || 0);
    const by = Number(best.cfgB.y_mm || 0);
    const tx = (bx - ax) / best.worldDist;
    const ty = (by - ay) / best.worldDist;
    const axisA = markerAxis(best.cfgA) || { x: 0, y: 1 };
    const axisB = markerAxis(best.cfgB) || axisA;
    let avgAx = axisA.x + axisB.x;
    let avgAy = axisA.y + axisB.y;
    const avgN = Math.hypot(avgAx, avgAy);
    if (avgN > 1e-6) {
      avgAx /= avgN;
      avgAy /= avgN;
    } else {
      avgAx = axisA.x;
      avgAy = axisA.y;
    }

    const n1x = -ty;
    const n1y = tx;
    const n2x = ty;
    const n2y = -tx;
    const useN2 = (n2x * avgAx + n2y * avgAy) > (n1x * avgAx + n1y * avgAy);
    const axisX = useN2 ? n2x : n1x;
    const axisY = useN2 ? n2y : n1y;

    const focalPx = Math.max(1, Number(RP.config.arucoFocalPx || 900));
    const defaultSizeMm = Math.max(10, Number(RP.config.arucoMarkerSizeCm || 15) * 10);
    const sizeA = Math.max(10, Number(best.cfgA.size_mm || defaultSizeMm));
    const sizeB = Math.max(10, Number(best.cfgB.size_mm || defaultSizeMm));
    const markerSizeMm = 0.5 * (sizeA + sizeB);
    const dPair = (focalPx * best.worldDist) / best.pixelDist;
    const areaA = Math.max(0, Number(best.da.area_px || 0));
    const areaB = Math.max(0, Number(best.db.area_px || 0));
    const avgArea = 0.5 * (areaA + areaB);
    let dArea = null;
    if (avgArea > 1) {
      dArea = (focalPx * markerSizeMm) / Math.sqrt(avgArea);
    }
    const estDist = Number.isFinite(dArea) ? ((0.85 * dPair) + (0.15 * dArea)) : dPair;
    const midX = 0.5 * (ax + bx);
    const midY = 0.5 * (ay + by);
    const poseX = midX + axisX * estDist;
    const poseY = midY + axisY * estDist;
    const thetaDeg = normalizeAngleDeg((Math.atan2(-axisY, -axisX) * 180) / Math.PI);
    return {
      idA: Number(best.da.id),
      idB: Number(best.db.id),
      pixelDist: best.pixelDist,
      worldDist: best.worldDist,
      estDist,
      poseX,
      poseY,
      thetaDeg,
    };
  }

  function logArucoRealtime(aruco) {
    if (!RP.config.arucoEnabled) return;
    if (!aruco || aruco.enabled === false) {
      if (RP.state.arucoHadDetection) {
        RP.utils.addLog("aruco: inactive (stream/off)");
      }
      RP.state.arucoHadDetection = false;
      RP.state.arucoLogSignature = "inactive";
      RP.state.arucoPairLogSignature = "";
      return;
    }
    if (!aruco.ok) {
      const reason = String(aruco.reason || "idle");
      const sig = `off:${reason}`;
      if (sig !== RP.state.arucoLogSignature) {
        RP.utils.addLog(`aruco: off (${reason})`);
      }
      RP.state.arucoHadDetection = false;
      RP.state.arucoLogSignature = sig;
      RP.state.arucoPairLogSignature = "";
      return;
    }
    const markers = Array.isArray(aruco.markers) ? aruco.markers : [];
    const ids = markers
      .map((m) => Number(m && m.id))
      .filter((v) => Number.isFinite(v))
      .sort((a, b) => a - b);
    const sig = `ok:${ids.join(",")}`;
    if (ids.length > 0 && sig !== RP.state.arucoLogSignature) {
      RP.utils.addLog(`aruco: detected ${ids.length} marker(s) [${ids.join(",")}]`);
      RP.state.arucoHadDetection = true;
    } else if (ids.length === 0 && RP.state.arucoHadDetection) {
      RP.utils.addLog("aruco: no marker");
      RP.state.arucoHadDetection = false;
    }
    const pair = computeArucoPairEstimate(aruco);
    if (pair) {
      const pairSig = `pair:${pair.idA}-${pair.idB}:${Math.round(pair.pixelDist)}:${Math.round(pair.estDist)}:${Math.round(pair.thetaDeg)}`;
      if (pairSig !== RP.state.arucoPairLogSignature) {
        RP.utils.addLog(
          `aruco pair ${pair.idA}-${pair.idB}: px=${pair.pixelDist.toFixed(1)} world=${Math.round(pair.worldDist)}mm estDist=${Math.round(pair.estDist)}mm estPose x=${Math.round(pair.poseX)} y=${Math.round(pair.poseY)} th=${Math.round(pair.thetaDeg)}deg`
        );
      }
      RP.state.arucoPairLogSignature = pairSig;
    }
    RP.state.arucoLogSignature = sig;
  }

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
        const batteryCharge = Number(data.battery_charge_mah || 0);
        const batteryCapacity = Number(data.battery_capacity_mah || 0);
        RP.refs.batteryMahNode.textContent = `${batteryCharge} / ${batteryCapacity}`;
        const chargingState = String(data.state || "unknown");
        const chargingCode = String(data.charging_state_code ?? "?");
        RP.refs.robotStateNode.textContent = `${chargingState} (code ${chargingCode})`;

        const bumpLeft = Boolean(data.bump_left);
        const bumpRight = Boolean(data.bump_right);
        const bumpAny = Boolean(data.bumper);
        RP.state.bumpLeft = bumpLeft;
        RP.state.bumpRight = bumpRight;
        RP.utils.setTextPill(RP.refs.bumperStateNode, `L:${bumpLeft ? "1" : "0"} R:${bumpRight ? "1" : "0"}`, bumpLeft || bumpRight);
        RP.utils.setPill(RP.refs.bumperAnyStateNode, bumpAny);

        const wdLeft = Boolean(data.wheel_drop_left);
        const wdRight = Boolean(data.wheel_drop_right);
        const wdCaster = Boolean(data.wheel_drop_caster);
        const wheelDropAny = wdLeft || wdRight || wdCaster;
        RP.utils.setTextPill(RP.refs.wheelDropStateNode, `L:${wdLeft ? "1" : "0"} R:${wdRight ? "1" : "0"} C:${wdCaster ? "1" : "0"}`, wheelDropAny);
        RP.utils.setPill(RP.refs.wheelDropAnyStateNode, wheelDropAny);

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
        RP.utils.setPill(RP.refs.wallStateNode, wallSeen);
        RP.utils.setPill(RP.refs.dockStateNode, dockVisible);
        RP.utils.setPill(RP.refs.linkStateNode, Boolean(data.roomba_connected));
        RP.refs.distanceStepMmNode.textContent = `${Number(data.distance_mm || 0)} mm`;
        RP.refs.angleStepDegNode.textContent = `${Number(data.angle_deg || 0)} deg`;
        RP.refs.totalDistanceMmNode.textContent = `${Number(data.total_distance_mm || 0)} mm`;
        RP.refs.totalAngleDegNode.textContent = `${Number(data.total_angle_deg || 0)} deg`;
        const leftEnc = Number(data.left_encoder_counts || 0);
        const rightEnc = Number(data.right_encoder_counts || 0);
        RP.refs.encoderCountsNode.textContent = `L:${leftEnc} R:${rightEnc}`;

        if (data.odometry) {
          RP.state.currentOdom = data.odometry;
          if (RP.map && typeof RP.map.setTargetPose === "function") {
            RP.map.setTargetPose(data.odometry);
          } else {
            RP.map.drawRobotPose();
          }
        }
        if (RP.aruco && typeof RP.aruco.updateFromTelemetry === "function") {
          const arucoPayload = data.aruco || null;
          RP.aruco.updateFromTelemetry(arucoPayload);
          logArucoRealtime(arucoPayload);
        }
      } catch (_) {
        RP.utils.addLog(`telemetry parse error: ${evt.data}`);
      }
    };
  }

  RP.telemetry = { connectTelemetry };
})();
