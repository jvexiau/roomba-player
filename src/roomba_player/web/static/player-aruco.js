(function () {
  const RP = window.RP;

  function resizeOverlay() {
    const img = RP.refs.cameraFeed;
    const canvas = RP.refs.cameraOverlay;
    if (!img || !canvas) return;
    const w = Math.max(1, Number(img.clientWidth || 0));
    const h = Math.max(1, Number(img.clientHeight || 0));
    const dpr = Math.max(1, Number(window.devicePixelRatio || 1));
    const pxW = Math.max(1, Math.round(w * dpr));
    const pxH = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== pxW) canvas.width = pxW;
    if (canvas.height !== pxH) canvas.height = pxH;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    canvas.style.left = `${Number(img.offsetLeft || 0)}px`;
    canvas.style.top = `${Number(img.offsetTop || 0)}px`;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  function clearOverlay() {
    const canvas = RP.refs.cameraOverlay;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
  }

  function drawMarkers(markers, sourceWidth, sourceHeight) {
    const canvas = RP.refs.cameraOverlay;
    if (!canvas) return;
    resizeOverlay();
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    clearOverlay();
    if (!Array.isArray(markers) || !markers.length) return;
    const srcW = Math.max(1, Number(sourceWidth || 1));
    const srcH = Math.max(1, Number(sourceHeight || 1));
    const rect = canvas.getBoundingClientRect();
    const scaleX = rect.width / srcW;
    const scaleY = rect.height / srcH;
    const flipX = RP.config.arucoOverlayFlipX !== false;
    const mapX = (x) => ((flipX ? (srcW - Number(x || 0)) : Number(x || 0)) * scaleX);
    const mapY = (y) => (Number(y || 0) * scaleY);
    ctx.lineWidth = 2;
    ctx.font = "14px sans-serif";
    markers.forEach((m) => {
      const pts = Array.isArray(m.corners) ? m.corners : [];
      if (pts.length !== 4) return;
      ctx.strokeStyle = "#22d3ee";
      ctx.fillStyle = "#22d3ee";
      ctx.beginPath();
      ctx.moveTo(mapX(pts[0][0]), mapY(pts[0][1]));
      for (let i = 1; i < pts.length; i += 1) {
        ctx.lineTo(mapX(pts[i][0]), mapY(pts[i][1]));
      }
      ctx.closePath();
      ctx.stroke();
      const center = Array.isArray(m.center) ? m.center : [pts[0][0], pts[0][1]];
      const cx = mapX(center[0]);
      const cy = mapY(center[1]);
      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText(`id:${m.id}`, cx + 6, cy - 6);
    });
  }

  function updateFromTelemetry(aruco) {
    if (!RP.config.arucoEnabled) {
      RP.refs.arucoStatusNode.textContent = "disabled";
      clearOverlay();
      return;
    }
    if (!aruco || aruco.enabled === false) {
      RP.refs.arucoStatusNode.textContent = "inactive";
      clearOverlay();
      return;
    }
    if (!aruco.ok) {
      RP.refs.arucoStatusNode.textContent = `off (${aruco.reason || "idle"})`;
      clearOverlay();
      return;
    }
    RP.refs.arucoStatusNode.textContent = `${Number(aruco.count || 0)} marker(s)`;
    drawMarkers(aruco.markers || [], aruco.frame_width, aruco.frame_height);
  }

  function startArucoIfEnabled() {
    if (!RP.config.arucoEnabled) {
      RP.refs.arucoStatusNode.textContent = "disabled";
      clearOverlay();
      return;
    }
    RP.refs.arucoStatusNode.textContent = "waiting stream";
    resizeOverlay();
  }

  RP.aruco = { startArucoIfEnabled, resizeOverlay, clearOverlay, updateFromTelemetry };
})();
