(function () {
  const config = window.ROOMBA_PLAYER_CONFIG || {};
  const refs = {
    controlStatus: document.getElementById("ctrlStatus"),
    telemetryStatus: document.getElementById("telemetryStatus"),
    logNode: document.getElementById("log"),
    speedSlider: document.getElementById("speedSlider"),
    speedValue: document.getElementById("speedValue"),
    cameraFeed: document.getElementById("cameraFeed"),
    cameraMessage: document.getElementById("cameraMessage"),
    activeInputsNode: document.getElementById("activeInputs"),
    executedCommandNode: document.getElementById("executedCommand"),
    batteryPctNode: document.getElementById("batteryPct"),
    batteryBar: document.getElementById("batteryBar"),
    robotStateNode: document.getElementById("robotState"),
    bumperStateNode: document.getElementById("bumperState"),
    wheelDropStateNode: document.getElementById("wheelDropState"),
    cliffStateNode: document.getElementById("cliffState"),
    chargingSourceStateNode: document.getElementById("chargingSourceState"),
    dockStateNode: document.getElementById("dockState"),
    linkStateNode: document.getElementById("linkState"),
    telemetryTsNode: document.getElementById("telemetryTs"),
    planStaticCanvas: document.getElementById("planStaticCanvas"),
    planRobotCanvas: document.getElementById("planRobotCanvas"),
    poseTextNode: document.getElementById("poseText"),
    planFileInput: document.getElementById("planFile"),
  };

  const state = {
    controlWs: null,
    telemetryWs: null,
    activeInputs: new Set(),
    lastCommandSignature: "",
    currentPlan: null,
    planProjection: null,
    odomPollTimer: null,
    currentOdom: { x_mm: 0, y_mm: 0, theta_deg: 0 },
    bumpLeft: false,
    bumpRight: false,
  };

  window.RP = { config, refs, state };
})();
