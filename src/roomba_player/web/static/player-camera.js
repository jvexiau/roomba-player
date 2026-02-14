(function () {
  const RP = window.RP;

  async function startCameraIfEnabled() {
    if (!RP.config.cameraEnabled) {
      RP.refs.cameraMessage.textContent = "Camera stream disabled.";
      return;
    }
    const baseUrl = "/camera/stream";
    let retryTimer = null;

    const ensureStarted = async () => {
      try {
        const r = await fetch("/camera/start", { method: "POST" });
        const j = await r.json();
        RP.utils.addLog(`camera/start -> ${JSON.stringify(j)}`);
      } catch (_) {
        RP.utils.addLog("camera start request failed");
      }
    };

    const scheduleRetry = () => {
      if (retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        ensureStarted().finally(() => {
          const sep = baseUrl.includes("?") ? "&" : "?";
          RP.refs.cameraFeed.src = `${baseUrl}${sep}t=${Date.now()}`;
        });
      }, 1200);
    };

    await ensureStarted();
    RP.refs.cameraMessage.textContent = "Camera stream loading...";
    RP.refs.cameraFeed.src = `${baseUrl}?t=${Date.now()}`;
    RP.refs.cameraFeed.style.display = "block";
    RP.refs.cameraFeed.onload = () => {
      RP.refs.cameraMessage.style.display = "none";
    };
    RP.refs.cameraFeed.onerror = () => {
      RP.refs.cameraMessage.style.display = "block";
      RP.refs.cameraMessage.textContent = "Camera stream unavailable (retrying...)";
      scheduleRetry();
    };
  }

  RP.camera = { startCameraIfEnabled };
})();
