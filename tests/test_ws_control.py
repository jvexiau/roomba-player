from roomba_player.ws import handle_control_message


class FakeRoomba:
    def __init__(self) -> None:
        self.connected = False
        self.mode = "safe"
        self.velocity = 0
        self.radius = 0
        self.cleaned = False
        self.docked = False
        self.bump_left = False
        self.bump_right = False

    def connect(self) -> None:
        self.connected = True

    def start(self) -> None:
        self.connected = True

    def start_sensor_stream(self) -> None:
        self.connected = True

    def safe(self) -> None:
        self.mode = "safe"

    def full(self) -> None:
        self.mode = "full"

    def drive(self, velocity: int, radius: int) -> None:
        self.velocity = velocity
        self.radius = radius

    def stop(self) -> None:
        self.velocity = 0
        self.radius = 0

    def clean(self) -> None:
        self.cleaned = True

    def dock(self) -> None:
        self.docked = True

    def get_telemetry_snapshot(self) -> dict:
        return {"bump_left": self.bump_left, "bump_right": self.bump_right}


def test_ws_control_init_and_drive() -> None:
    roomba = FakeRoomba()

    init_result = handle_control_message({"action": "init"}, roomba)
    assert init_result["ok"] is True
    assert init_result["connected"] is True

    drive_result = handle_control_message({"action": "drive", "velocity": 200, "radius": 1}, roomba)
    assert drive_result["ok"] is True
    assert drive_result["velocity"] == 200
    assert drive_result["radius"] == 1


def test_ws_control_unknown_action() -> None:
    roomba = FakeRoomba()
    try:
        handle_control_message({"action": "invalid"}, roomba)
    except ValueError as exc:
        assert "Unsupported action" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown action")


def test_ws_control_bumper_guard_blocks_forward() -> None:
    roomba = FakeRoomba()
    roomba.bump_left = True
    result = handle_control_message({"action": "drive", "velocity": 200, "radius": 32768}, roomba)
    assert result["ok"] is True
    assert result.get("guarded") is True
    assert result["velocity"] == 0
    assert result["radius"] == 32768


def test_ws_control_both_bumpers_block_forward() -> None:
    roomba = FakeRoomba()
    roomba.bump_left = True
    roomba.bump_right = True
    result = handle_control_message({"action": "drive", "velocity": 200, "radius": 32768}, roomba)
    assert result["ok"] is True
    assert result.get("guarded") is True
    assert result["velocity"] == 0
    assert result["radius"] == 32768


def test_ws_control_single_bumper_blocks_forward_arc() -> None:
    roomba = FakeRoomba()
    roomba.bump_right = True
    result = handle_control_message({"action": "drive", "velocity": 180, "radius": 220}, roomba)
    assert result["ok"] is True
    assert result.get("guarded") is True
    assert result["velocity"] == 0
