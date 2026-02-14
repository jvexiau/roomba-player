(function () {
  const RP = window.RP;

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

  function renderStaticPlan() {
    const c = RP.refs.planStaticCanvas;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, c.width, c.height);
    RP.state.planProjection = null;
    if (!RP.state.currentPlan) return;

    const b = computePlanBounds(RP.state.currentPlan);
    const pad = 20;
    const sx = (c.width - pad * 2) / Math.max(1, b.maxX - b.minX);
    const sy = (c.height - pad * 2) / Math.max(1, b.maxY - b.minY);
    const scale = Math.min(sx, sy);
    const h = c.height;
    const tx = (x, s) => pad + (x - b.minX) * s;
    const ty = (y, s) => h - pad - (y - b.minY) * s;
    RP.state.planProjection = { minX: b.minX, minY: b.minY, pad, scale, height: h };

    ctx.lineWidth = 2;
    RP.utils.drawPolygon(ctx, RP.state.currentPlan.contour, tx, ty, scale, "#334155", "#f8fafc");
    const shapes = RP.state.currentPlan.object_shapes || {};
    for (const obj of RP.state.currentPlan.objects || []) {
      const shape = shapes[obj.shape_ref];
      if (!shape) continue;
      const theta = ((obj.theta_deg || 0) * Math.PI) / 180;
      const pts = (shape.contour || []).map((p) => {
        const r = RP.utils.rotatePoint(p[0], p[1], theta);
        return [r[0] + (obj.x_mm || 0), r[1] + (obj.y_mm || 0)];
      });
      RP.utils.drawPolygon(ctx, pts, tx, ty, scale, "#94a3b8", "#e2e8f0");
    }
  }

  function drawRobotPose() {
    const c = RP.refs.planRobotCanvas;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    const odom = RP.state.currentOdom || { x_mm: 0, y_mm: 0, theta_deg: 0 };
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

  async function refreshPlan() {
    try {
      const r = await fetch("/api/plan");
      const j = await r.json();
      RP.state.currentPlan = j.plan || null;
    } catch (_) {
      RP.state.currentPlan = null;
    }
    renderStaticPlan();
    drawRobotPose();
  }

  RP.map = {
    drawRobotPose,
    refreshPlan,
  };
})();
