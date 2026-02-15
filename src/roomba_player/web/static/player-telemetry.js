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

  function markerObservedSizePx(marker) {
    const pts = Array.isArray(marker && marker.corners) ? marker.corners : [];
    if (pts.length !== 4) return null;
    const edges = [];
    for (let i = 0; i < 4; i += 1) {
      const a = pts[i];
      const b = pts[(i + 1) % 4];
      edges.push(Math.hypot(Number(b[0] || 0) - Number(a[0] || 0), Number(b[1] || 0) - Number(a[1] || 0)));
    }
    if (!edges.length) return null;
    return edges.reduce((acc, v) => acc + v, 0) / edges.length;
  }

  function markerShapeMetrics(marker) {
    const pts = Array.isArray(marker && marker.corners) ? marker.corners : [];
    if (pts.length !== 4) return { shapeCos: 1, shapeYawDeg: 0, widthPx: 0, heightPx: 0 };
    const p = pts.map((it) => [Number(it[0] || 0), Number(it[1] || 0)]);
    const e01 = Math.hypot(p[1][0] - p[0][0], p[1][1] - p[0][1]);
    const e12 = Math.hypot(p[2][0] - p[1][0], p[2][1] - p[1][1]);
    const e23 = Math.hypot(p[3][0] - p[2][0], p[3][1] - p[2][1]);
    const e30 = Math.hypot(p[0][0] - p[3][0], p[0][1] - p[3][1]);
    const widthPx = 0.5 * (e01 + e23);
    const heightPx = 0.5 * (e12 + e30);
    if (widthPx <= 1e-6 || heightPx <= 1e-6) return { shapeCos: 1, shapeYawDeg: 0, widthPx, heightPx };
    const shapeCos = Math.max(0.08, Math.min(1, Math.min(widthPx, heightPx) / Math.max(widthPx, heightPx)));
    const yawAbsDeg = (Math.acos(Math.max(0, Math.min(1, shapeCos))) * 180) / Math.PI;
    const lrDiff = e12 - e30;
    const shapeYawDeg = Math.abs(lrDiff) < 1e-3 ? 0 : (lrDiff > 0 ? yawAbsDeg : -yawAbsDeg);
    return { shapeCos, shapeYawDeg, widthPx, heightPx };
  }

  function markerEstimate(markerCfg, marker, frameWidth) {
    if (!markerCfg) return null;
    const axis = markerAxis(markerCfg);
    if (!axis) return null;
    const markerX = Number(markerCfg.x_mm || 0);
    const markerY = Number(markerCfg.y_mm || 0);
    const areaPx = Math.max(0, Number(marker.area_px || 0));
    const focalPx = Math.max(1, Number(RP.config.arucoFocalPx || 900));
    const sizeMm = Math.max(10, Number(markerCfg.size_mm || (Number(RP.config.arucoMarkerSizeCm || 15) * 10)));
    const markerPx = markerObservedSizePx(marker);
    const shape = markerShapeMetrics(marker);

    let estDist = Number(markerCfg.front_offset_mm || 250);
    if (areaPx > 1) {
      const areaAnchor = 3253 * ((sizeMm / 150) ** 2);
      estDist = 150 * (sizeMm / 150) * Math.sqrt(Math.max(1, areaAnchor) / areaPx);
      estDist *= Math.sqrt(shape.shapeCos);
    } else if (markerPx && markerPx > 1) {
      estDist = ((focalPx * sizeMm) / markerPx) * 0.18;
    }
    estDist = Math.max(70, Math.min(2500, estDist));

    const targetX = markerX + axis.x * estDist;
    const targetY = markerY + axis.y * estDist;
    const baseHeading = (Math.atan2(-axis.y, -axis.x) * 180) / Math.PI;
    const center = Array.isArray(marker.center) ? marker.center : [frameWidth * 0.5, 0];
    const cx = Number(center[0] || (frameWidth * 0.5));
    const fw = Math.max(1, Number(frameWidth || 1));
    let proximity = 0;
    if (areaPx > 1) proximity = Math.max(0, Math.min(1, areaPx / 3253));
    else if (markerPx) proximity = Math.max(0, Math.min(1, (markerPx - 20) / 120));
    const headingOffset = ((cx / fw) - 0.5) * (8.0 * (0.2 * (1 - proximity)));
    const shapeHeadingCorrection = shape.shapeYawDeg * (0.33 * (1 - 0.5 * proximity));
    const targetTheta = normalizeAngleDeg(baseHeading + headingOffset + shapeHeadingCorrection);
    return {
      estDist,
      targetX,
      targetY,
      targetTheta,
      markerPx,
      shapeCos: shape.shapeCos,
      shapeYawDeg: shape.shapeYawDeg,
      widthPx: shape.widthPx,
      heightPx: shape.heightPx,
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
      RP.state.arucoFrameLogKey = "";
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
      RP.state.arucoFrameLogKey = "";
      return;
    }
    const markers = Array.isArray(aruco.markers) ? aruco.markers : [];
    const markerKey = markers
      .map((m) => `${Number(m && m.id)}:${Math.round(Number((m && m.area_px) || 0))}`)
      .sort()
      .join(",");
    const frameKey = `${String(aruco.timestamp || "none")}|${Number(aruco.frame_width || 0)}x${Number(aruco.frame_height || 0)}|${markerKey}`;
    if (frameKey !== RP.state.arucoFrameLogKey) {
      const frameW = Number(aruco.frame_width || 0);
      const frameH = Number(aruco.frame_height || 0);
      const status = markers.length > 0 ? "FOUND" : "NOT_FOUND";
      RP.utils.addLog(`aruco frame ts=${String(aruco.timestamp || "-")} size=${frameW}x${frameH} status=${status} markers=${markers.length}`);
      const plan = RP.state.currentPlan;
      const cfgById = new Map();
      if (plan && Array.isArray(plan.aruco_markers)) {
        for (const cfg of plan.aruco_markers) {
          const id = Number(cfg && cfg.id);
          if (Number.isFinite(id)) cfgById.set(id, cfg);
        }
      }
      if (markers.length === 0) {
        RP.utils.addLog("  - no marker detected on this analysis");
      } else {
        for (const marker of markers) {
          const id = Number(marker && marker.id);
          if (!Number.isFinite(id)) continue;
          const center = Array.isArray(marker.center) ? marker.center : [0, 0];
          const areaPx = Number(marker.area_px || 0);
          const cfg = cfgById.get(id);
          const est = markerEstimate(cfg, marker, frameW);
          if (!cfg || !est) {
            RP.utils.addLog(
              `  - id=${id} center=(${Number(center[0] || 0).toFixed(1)},${Number(center[1] || 0).toFixed(1)}) area=${Math.round(areaPx)} (no plan marker cfg)`
            );
            continue;
          }
          const odom = RP.state.currentOdom || { x_mm: 0, y_mm: 0 };
          const dx = est.targetX - Number(odom.x_mm || 0);
          const dy = est.targetY - Number(odom.y_mm || 0);
          const dd = Math.hypot(dx, dy);
          RP.utils.addLog(
            `  - id=${id} center=(${Number(center[0] || 0).toFixed(1)},${Number(center[1] || 0).toFixed(1)}) area=${Math.round(areaPx)} pxSize=${(est.markerPx || 0).toFixed(1)} shapeCos=${est.shapeCos.toFixed(3)} shapeYaw=${est.shapeYawDeg.toFixed(1)}deg estDist=${Math.round(est.estDist)}mm estPose=(${Math.round(est.targetX)},${Math.round(est.targetY)},${Math.round(est.targetTheta)}deg) relToOdom=(${Math.round(dx)},${Math.round(dy)} d=${Math.round(dd)}mm)`
          );
        }
      }
      RP.state.arucoFrameLogKey = frameKey;
    }
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
