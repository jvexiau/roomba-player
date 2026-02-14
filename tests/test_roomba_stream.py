from roomba_player.roomba import RoombaOI


def test_stream_payload_updates_telemetry() -> None:
    roomba = RoombaOI(port="/dev/null", baudrate=115200, timeout=1.0)

    payload = bytes(
        [
            7,
            0x03,  # bumper left+right
            21,
            0x02,  # full_charging
            25,
            0x01,
            0xF4,  # charge=500
            26,
            0x03,
            0xE8,  # capacity=1000
            34,
            0x02,  # dock visible (home base)
        ]
    )

    roomba._apply_stream_payload(payload)
    snapshot = roomba.get_telemetry_snapshot()

    assert snapshot["bumper"] is True
    assert snapshot["state"] == "full_charging"
    assert snapshot["battery_charge_mah"] == 500
    assert snapshot["battery_capacity_mah"] == 1000
    assert snapshot["battery_pct"] == 50
    assert snapshot["dock_visible"] is True
