from roomba_player.app import _compute_aruco_pair_target_pose, _compute_aruco_target_pose


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
        "area_px": 3253,
        "corners": [[270, 190], [370, 190], [370, 290], [270, 290]],  # ~100px edges
    }
    pose = _compute_aruco_target_pose(marker_cfg, marker_detection, frame_width=640)
    assert pose is not None
    x_mm, y_mm, theta_deg, pos_blend, theta_blend = pose
    assert round(x_mm, 3) == 1000.0
    # Calibration anchor: area 3253 px² => distance ~150mm from marker.
    assert round(y_mm, 3) == 2150.0
    # Facing marker (axis +Y => heading about -90deg).
    assert -100.0 <= theta_deg <= -80.0
    assert 0.9 <= pos_blend <= 1.0
    assert 0.9 <= theta_blend <= 1.0


def test_compute_aruco_target_pose_uses_shape_for_oblique_distance_and_heading() -> None:
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
        "area_px": 3253,
        # Oblique shape: narrow width and right edge slightly larger than left.
        "corners": [[295, 190], [345, 190], [355, 290], [300, 290]],
    }
    pose = _compute_aruco_target_pose(marker_cfg, marker_detection, frame_width=640)
    assert pose is not None
    x_mm, y_mm, theta_deg, _pos_blend, _theta_blend = pose
    assert round(x_mm, 3) == 1000.0
    # Oblique rectangle should infer closer distance than frontal 150mm anchor.
    assert y_mm < 2150.0
    # Right side visually nearer => heading correction should move above frontal -90deg.
    assert theta_deg > -90.0


def test_compute_aruco_pair_target_pose_uses_two_markers_spacing() -> None:
    marker_a_cfg = {
        "id": 10,
        "x_mm": 1000,
        "y_mm": 3000,
        "theta_deg": 90,
        "size_mm": 150,
    }
    marker_b_cfg = {
        "id": 11,
        "x_mm": 1150,
        "y_mm": 3000,
        "theta_deg": 90,
        "size_mm": 150,
    }
    marker_a_detection = {
        "id": 10,
        "center": [260, 240],
        "area_px": 3200,
        "corners": [[225, 205], [295, 205], [295, 275], [225, 275]],
    }
    marker_b_detection = {
        "id": 11,
        "center": [420, 240],
        "area_px": 3200,
        "corners": [[385, 205], [455, 205], [455, 275], [385, 275]],
    }
    pose = _compute_aruco_pair_target_pose(
        marker_a_cfg,
        marker_a_detection,
        marker_b_cfg,
        marker_b_detection,
        frame_width=640,
    )
    assert pose is not None
    x_mm, y_mm, theta_deg, pos_blend, theta_blend = pose
    # Pair midpoint is x=1075mm; we expect a strong forward offset on +Y axis.
    assert 1000.0 <= x_mm <= 1150.0
    assert y_mm > 3000.0
    # Robot should face the pair (heading around -90deg).
    assert -110.0 <= theta_deg <= -70.0
    assert 0.92 <= pos_blend <= 1.0
    assert 0.94 <= theta_blend <= 1.0


def test_compute_aruco_target_pose_front_shape_forces_hard_front_snap() -> None:
    marker_cfg = {
        "id": 12,
        "x_mm": 500,
        "y_mm": 1200,
        "size_mm": 150,
        "snap_pose": {"x_mm": 500, "y_mm": 1500},  # axis +Y => frontal heading about -90deg
    }
    marker_detection = {
        "id": 12,
        "center": [320, 240],
        "area_px": 3200,
        # Near-square frontal projection.
        "corners": [[270, 190], [370, 190], [370, 290], [270, 290]],
    }
    pose = _compute_aruco_target_pose(marker_cfg, marker_detection, frame_width=640)
    assert pose is not None
    _x_mm, _y_mm, theta_deg, pos_blend, theta_blend = pose
    assert -92.0 <= theta_deg <= -88.0
    assert pos_blend == 1.0
    assert theta_blend == 1.0
