(function () {
  const RP = window.RP;
  const defaultPose = { x_mm: 0, y_mm: 0, theta_deg: 0 };
  let targetPose = { ...defaultPose };
  let renderPose = { ...defaultPose };
  let animLoopStarted = false;
  let lastAnimTs = 0;
  let resizeBound = false;

  function computePlanBounds(plan) {
    const pts = [].concat(plan.contour || []);
    const shapes = plan.object_shapes || {};
    for (const obj of plan.objects || []) {
      const shape = shapes[obj.shape_ref];
      if (!shape || !Array.isArray(shape.contour)) continue;
      const theta = ((obj.theta_deg || 0) * Math.PI) / 180;
      for (const p of shape.contour) {
        const rotated = RP.utils.rotatePoint(p[0], p[1], theta);
        pts.push([rotated[0] + (obj.x_mm || 0), rotated[1] + (obj.y_mm || 0)]);
      }
    }
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function applyCanvasSize(bounds) {
    const staticCanvas = RP.refs.planStaticCanvas;
    const robotCanvas = RP.refs.planRobotCanvas;
    const host = staticCanvas.parentElement;
    const hostWidth = Math.max(320, Math.floor((host && host.clientWidth) || staticCanvas.clientWidth || 900));
    const defaultAspect = 0.58;
    let aspect = defaultAspect;
    if (bounds) {
      const w = Math.max(1, bounds.maxX - bounds.minX);
      const h = Math.max(1, bounds.maxY - bounds.minY);
      aspect = h / w;
    }
    const maxH = clamp(Math.floor(window.innerHeight * 0.82), 420, 1200);
    const minH = 340;
    const targetH = clamp(Math.round(hostWidth * aspect), minH, maxH);
    if (staticCanvas.width !== hostWidth || staticCanvas.height !== targetH) {
      staticCanvas.width = hostWidth;
      staticCanvas.height = targetH;
      robotCanvas.width = hostWidth;
      robotCanvas.height = targetH;
    }
  }

  function renderStaticPlan() {
    const c = RP.refs.planStaticCanvas;
    const plan = RP.state.currentPlan;
    const b = plan ? computePlanBounds(plan) : null;
    applyCanvasSize(b);
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, c.width, c.height);
    RP.state.planProjection = null;
    if (!plan) return;

    const pad = 20;
    const sx = (c.width - pad * 2) / Math.max(1, b.maxX - b.minX);
    const sy = (c.height - pad * 2) / Math.max(1, b.maxY - b.minY);
    const scale = Math.min(sx, sy);
    const h = c.height;
    const tx = (x, s) => pad + (x - b.minX) * s;
    const ty = (y, s) => h - pad - (y - b.minY) * s;
    RP.state.planProjection = { minX: b.minX, minY: b.minY, pad, scale, height: h };

    ctx.lineWidth = 2;
    RP.utils.drawPolygon(ctx, plan.contour, tx, ty, scale, "#334155", "#f8fafc");
    const shapes = plan.object_shapes || {};
    for (const obj of plan.objects || []) {
      const shape = shapes[obj.shape_ref];
      if (!shape) continue;
      const theta = ((obj.theta_deg || 0) * Math.PI) / 180;
      const pts = (shape.contour || []).map((p) => {
        const r = RP.utils.rotatePoint(p[0], p[1], theta);
        return [r[0] + (obj.x_mm || 0), r[1] + (obj.y_mm || 0)];
      });
      RP.utils.drawPolygon(ctx, pts, tx, ty, scale, "#94a3b8", "#e2e8f0");
    }

    const arucoMarkers = Array.isArray(plan.aruco_markers) ? plan.aruco_markers : [];
    if (arucoMarkers.length) {
      ctx.font = "10px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "bottom";
      for (const marker of arucoMarkers) {
        const mx = Number(marker.x_mm || 0);
        const my = Number(marker.y_mm || 0);
        const id = marker.id != null ? String(marker.id) : "?";
        const sx = tx(mx, scale);
        const sy = ty(my, scale);
        ctx.fillStyle = "#0f766e";
        ctx.beginPath();
        ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#134e4a";
        ctx.fillText(id, sx + 4, sy - 2);
      }
    }
  }

  function normalizeAngleDeg(angle) {
    let a = Number(angle || 0);
    while (a > 180) a -= 360;
    while (a < -180) a += 360;
    return a;
  }

  function drawRobotPoseFrom(pose) {
    const c = RP.refs.planRobotCanvas;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    const odom = pose || defaultPose;
    RP.refs.poseTextNode.textContent = `x=${Math.round(odom.x_mm || 0)} y=${Math.round(odom.y_mm || 0)} θ=${Math.round(odom.theta_deg || 0)}°`;
    const p = RP.state.planProjection;
    if (!p) return;
    const rx = p.pad + ((odom.x_mm || 0) - p.minX) * p.scale;
    const ry = p.height - p.pad - ((odom.y_mm || 0) - p.minY) * p.scale;
    const theta = ((odom.theta_deg || 0) * Math.PI) / 180;
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

  function animationTick(ts) {
    if (!lastAnimTs) lastAnimTs = ts;
    const dt = Math.max(0.001, Math.min(0.05, (ts - lastAnimTs) / 1000));
    lastAnimTs = ts;
    const posAlpha = 1 - Math.exp(-16 * dt);
    const angAlpha = 1 - Math.exp(-18 * dt);
    renderPose.x_mm += (targetPose.x_mm - renderPose.x_mm) * posAlpha;
    renderPose.y_mm += (targetPose.y_mm - renderPose.y_mm) * posAlpha;
    const dTheta = normalizeAngleDeg(targetPose.theta_deg - renderPose.theta_deg);
    renderPose.theta_deg = normalizeAngleDeg(renderPose.theta_deg + dTheta * angAlpha);
    drawRobotPoseFrom(renderPose);
    window.requestAnimationFrame(animationTick);
  }

  function ensureAnimationLoop() {
    if (animLoopStarted) return;
    animLoopStarted = true;
    window.requestAnimationFrame(animationTick);
    if (!resizeBound) {
      resizeBound = true;
      window.addEventListener("resize", () => {
        renderStaticPlan();
        drawRobotPoseFrom(renderPose);
      });
    }
  }

  function setTargetPose(odom) {
    const next = odom || defaultPose;
    targetPose = {
      x_mm: Number(next.x_mm || 0),
      y_mm: Number(next.y_mm || 0),
      theta_deg: Number(next.theta_deg || 0),
    };
    if (!animLoopStarted) {
      renderPose = { ...targetPose };
    }
  }

  function drawRobotPose() {
    setTargetPose(RP.state.currentOdom || defaultPose);
    drawRobotPoseFrom(renderPose);
  }

  async function refreshPlan() {
    try {
      const r = await fetch("/api/plan");
      const j = await r.json();
      RP.state.currentPlan = j.plan || null;
    } catch (_) {
      RP.state.currentPlan = null;
    }
    renderStaticPlan();
    setTargetPose(RP.state.currentOdom || defaultPose);
    drawRobotPoseFrom(renderPose);
    ensureAnimationLoop();
  }

  RP.map = {
    setTargetPose,
    drawRobotPose,
    refreshPlan,
  };
})();
