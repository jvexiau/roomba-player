from roomba_player.app import _compute_aruco_target_pose


def test_compute_aruco_target_pose_uses_marker_size_for_distance() -> None:
    marker_cfg = {
        "id": 54,
        "x_mm": 1000,
        "y_mm": 2000,
        "size_mm": 150,
        "snap_pose": {"x_mm": 1000, "y_mm": 2300},
    }
    marker_detection = {
        "id": 54,
        "center": [320, 240],
        "corners": [[270, 190], [370, 190], [370, 290], [270, 290]],  # ~100px edges
    }
    pose = _compute_aruco_target_pose(marker_cfg, marker_detection, frame_width=640)
    assert pose is not None
    x_mm, y_mm, theta_deg, pos_blend, theta_blend = pose
    assert round(x_mm, 3) == 1000.0
    # Vision estimate is strongly reduced and mildly anchored to base offset:
    # 1350 * 0.18 = 243mm, target = 243*0.8 + 300*0.2 = 254.4mm.
    assert round(y_mm, 3) == 2254.4
    # Facing marker (axis +Y => heading about -90deg).
    assert -100.0 <= theta_deg <= -80.0
    assert 0.85 <= pos_blend <= 1.0
    assert 0.8 <= theta_blend <= 1.0
