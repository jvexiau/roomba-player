(function () {
  const RP = window.RP;

  async function startCameraIfEnabled() {
    if (!RP.config.cameraEnabled) {
      RP.refs.cameraMessage.textContent = "Camera stream disabled.";
      return;
    }
    const baseUrl = "/camera/stream";
    const box = RP.refs.cameraBox;
    const srcW = Math.max(1, Number(RP.config.cameraWidth || 640));
    const srcH = Math.max(1, Number(RP.config.cameraHeight || 480));
    if (box) box.style.aspectRatio = `${srcW} / ${srcH}`;
    let retryTimer = null;

    const reloadStream = () => {
      const sep = baseUrl.includes("?") ? "&" : "?";
      RP.refs.cameraFeed.src = `${baseUrl}${sep}t=${Date.now()}`;
    };

    const scheduleRetry = () => {
      if (retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        reloadStream();
      }, 1200);
    };

    RP.refs.cameraFeed.onload = () => {
      RP.refs.cameraMessage.style.display = "none";
      if (RP.aruco && typeof RP.aruco.resizeOverlay === "function") {
        RP.aruco.resizeOverlay();
      }
    };
    RP.refs.cameraFeed.onerror = () => {
      RP.refs.cameraMessage.style.display = "block";
      RP.refs.cameraMessage.textContent = "Camera stream unavailable (retrying...)";
      scheduleRetry();
    };

    RP.refs.cameraMessage.style.display = "block";
    RP.refs.cameraMessage.textContent = "Camera stream loading...";
    RP.refs.cameraFeed.style.display = "block";
    if (RP.refs.cameraOverlay) RP.refs.cameraOverlay.style.display = "block";
    reloadStream();

    window.addEventListener("resize", () => {
      if (RP.aruco && typeof RP.aruco.resizeOverlay === "function") {
        RP.aruco.resizeOverlay();
      }
    });
  }

  RP.camera = { startCameraIfEnabled };
})();
