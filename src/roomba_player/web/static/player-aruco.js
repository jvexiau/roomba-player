(function () {
  const RP = window.RP;

  function resizeOverlay() {
    const img = RP.refs.cameraFeed;
    const canvas = RP.refs.cameraOverlay;
    if (!img || !canvas) return;
    const w = Math.max(1, Math.floor(img.clientWidth || 0));
    const h = Math.max(1, Math.floor(img.clientHeight || 0));
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
  }

  function clearOverlay() {
    const canvas = RP.refs.cameraOverlay;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function drawMarkers(markers, sourceWidth, sourceHeight) {
    const canvas = RP.refs.cameraOverlay;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    clearOverlay();
    if (!Array.isArray(markers) || !markers.length) return;
    const scaleX = canvas.width / Math.max(1, Number(sourceWidth || 1));
    const scaleY = canvas.height / Math.max(1, Number(sourceHeight || 1));
    ctx.lineWidth = 2;
    ctx.font = "14px sans-serif";
    markers.forEach((m) => {
      const pts = Array.isArray(m.corners) ? m.corners : [];
      if (pts.length !== 4) return;
      ctx.strokeStyle = "#22d3ee";
      ctx.fillStyle = "#22d3ee";
      ctx.beginPath();
      ctx.moveTo(pts[0][0] * scaleX, pts[0][1] * scaleY);
      for (let i = 1; i < pts.length; i += 1) {
        ctx.lineTo(pts[i][0] * scaleX, pts[i][1] * scaleY);
      }
      ctx.closePath();
      ctx.stroke();
      const center = Array.isArray(m.center) ? m.center : [pts[0][0], pts[0][1]];
      const cx = center[0] * scaleX;
      const cy = center[1] * scaleY;
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
