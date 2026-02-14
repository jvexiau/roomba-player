from roomba_player.roomba import RoombaOI


def test_stream_payload_updates_telemetry() -> None:
    roomba = RoombaOI(port="/dev/null", baudrate=115200, timeout=1.0)

    payload = bytes(
        [
            7,
            0x03,  # bumper left+right
            19,
            0x00,
            0x64,  # distance=100mm
            20,
            0x00,
            0x0A,  # angle=10deg
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
            43,
            0x12,
            0x34,
            44,
            0x56,
            0x78,
        ]
    )

    roomba._apply_stream_payload(payload)
    snapshot = roomba.get_telemetry_snapshot()

    assert snapshot["bumper"] is True
    assert snapshot["bump_left"] is True
    assert snapshot["bump_right"] is True
    assert snapshot["state"] == "full_charging"
    assert snapshot["battery_charge_mah"] == 500
    assert snapshot["battery_capacity_mah"] == 1000
    assert snapshot["battery_pct"] == 50
    assert snapshot["dock_visible"] is True
    assert snapshot["charging_source_home_base"] is True
    assert snapshot["charging_source_internal"] is False
    assert snapshot["distance_mm"] == 100
    assert snapshot["angle_deg"] == 10
    assert snapshot["total_distance_mm"] == 100
    assert snapshot["total_angle_deg"] == 10
    assert snapshot["left_encoder_counts"] == 0x1234
    assert snapshot["right_encoder_counts"] == 0x5678
