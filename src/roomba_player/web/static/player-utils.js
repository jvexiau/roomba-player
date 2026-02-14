(function () {
  const RP = window.RP;

  function wsUrl(path) {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}${path}`;
  }

  function addLog(line) {
    const ts = new Date().toLocaleTimeString();
    RP.refs.logNode.textContent = `[${ts}] ${line}\n` + RP.refs.logNode.textContent;
  }

  function setPill(node, ok) {
    node.innerHTML = ok
      ? '<span class="pill ok">yes</span>'
      : '<span class="pill warn">no</span>';
  }

  function setTextPill(node, text, ok) {
    node.innerHTML = ok
      ? `<span class="pill ok">${text}</span>`
      : `<span class="pill warn">${text}</span>`;
  }

  function rotatePoint(x, y, theta) {
    const c = Math.cos(theta);
    const s = Math.sin(theta);
    return [x * c - y * s, x * s + y * c];
  }

  function drawPolygon(ctx, points, tx, ty, scale, stroke, fill) {
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

  RP.utils = {
    wsUrl,
    addLog,
    setPill,
    setTextPill,
    rotatePoint,
    drawPolygon,
  };
})();
