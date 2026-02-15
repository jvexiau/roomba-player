import json

from roomba_player.history import JsonlHistoryStore
from roomba_player.odometry import OdometryEstimator


def test_odometry_from_sensor_totals() -> None:
    odom = OdometryEstimator()
    odom.update_from_telemetry({"total_distance_mm": 0, "total_angle_deg": 0, "timestamp": "t0"})
    pose = odom.update_from_telemetry({"total_distance_mm": 100, "total_angle_deg": 0, "timestamp": "t1"})
    assert round(pose["x_mm"], 3) == 100.0
    assert round(pose["y_mm"], 3) == 0.0

    pose = odom.update_from_telemetry({"total_distance_mm": 100, "total_angle_deg": 90, "timestamp": "t2"})
    assert round(pose["x_mm"], 3) == 100.0
    assert round(pose["y_mm"], 3) == 0.0
    assert round(pose["theta_deg"], 3) == 90.0

    pose = odom.update_from_telemetry({"total_distance_mm": 200, "total_angle_deg": 90, "timestamp": "t3"})
    assert round(pose["x_mm"], 3) == 100.0
    assert round(pose["y_mm"], 3) == 100.0


def test_odometry_history_jsonl(tmp_path) -> None:
    history_path = tmp_path / "bdd" / "odometry_history.jsonl"
    store = JsonlHistoryStore(str(history_path))
    odom = OdometryEstimator(history_sink=store.append)

    odom.reset(10, 20, 0)
    odom.update_from_telemetry({"total_distance_mm": 0, "total_angle_deg": 0, "timestamp": "t0"})
    odom.update_from_telemetry({"total_distance_mm": 30, "total_angle_deg": 5, "timestamp": "t1"})

    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    events = [json.loads(line) for line in lines]
    assert any(event.get("event") == "reset" for event in events)
    assert any(event.get("event") == "update" for event in events)
    pose = store.last_pose()
    assert pose is not None
    assert isinstance(pose["x_mm"], float)
    assert isinstance(pose["y_mm"], float)
    assert isinstance(pose["theta_deg"], float)
    store.clear()
    assert history_path.read_text(encoding="utf-8") == ""


def test_reset_anchors_sensor_baseline() -> None:
    odom = OdometryEstimator()
    odom.reset(4200, 7000, 0, base_total_distance_mm=1000, base_total_angle_deg=90)
    pose = odom.update_from_telemetry({"total_distance_mm": 1000, "total_angle_deg": 90, "timestamp": "t0"})
    assert round(pose["x_mm"], 3) == 4200.0
    assert round(pose["y_mm"], 3) == 7000.0
    assert round(pose["theta_deg"], 3) == 0.0


def test_odometry_from_encoder_counts_forward() -> None:
    odom = OdometryEstimator()
    odom.reset(0, 0, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry({"left_encoder_counts": 1100, "right_encoder_counts": 1100, "timestamp": "t1"})
    assert pose["x_mm"] > 40.0
    assert abs(pose["y_mm"]) < 1.0


def test_odometry_linear_scale_reduces_distance() -> None:
    odom_a = OdometryEstimator(source="distance_angle", linear_scale=1.0)
    odom_b = OdometryEstimator(source="distance_angle", linear_scale=0.5)
    odom_a.reset(0, 0, 0, base_total_distance_mm=1000, base_total_angle_deg=0)
    odom_b.reset(0, 0, 0, base_total_distance_mm=1000, base_total_angle_deg=0)
    pose_a = odom_a.update_from_telemetry({"total_distance_mm": 1200, "total_angle_deg": 0, "timestamp": "t1"})
    pose_b = odom_b.update_from_telemetry({"total_distance_mm": 1200, "total_angle_deg": 0, "timestamp": "t1"})
    assert pose_b["x_mm"] < pose_a["x_mm"]


def test_distance_angle_mode_uses_encoder_pose() -> None:
    odom = OdometryEstimator(source="distance_angle")
    odom.reset(
        0,
        0,
        0,
        base_total_distance_mm=1000,
        base_total_angle_deg=20,
        base_left_encoder_counts=2000,
        base_right_encoder_counts=2000,
    )
    pose = odom.update_from_telemetry(
        {
            "total_distance_mm": 1000,
            "total_angle_deg": 30,
            "left_encoder_counts": 2100,
            "right_encoder_counts": 2100,
            "timestamp": "t1",
        }
    )
    assert pose["x_mm"] > 40.0
    assert round(pose["theta_deg"], 3) == 10.0


def test_distance_angle_prefers_encoder_translation() -> None:
    odom = OdometryEstimator(source="distance_angle")
    odom.reset(
        0,
        0,
        0,
        base_total_distance_mm=1000,
        base_total_angle_deg=0,
        base_left_encoder_counts=2000,
        base_right_encoder_counts=2000,
    )
    pose = odom.update_from_telemetry(
        {
            "total_distance_mm": 1001,  # tiny OI distance delta
            "total_angle_deg": 0,
            "left_encoder_counts": 2200,
            "right_encoder_counts": 2200,
            "timestamp": "t1",
        }
    )
    assert pose["x_mm"] > 80.0


def test_bump_freezes_encoder_odometry_step() -> None:
    odom = OdometryEstimator(source="encoders")
    odom.reset(0, 0, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry(
        {
            "left_encoder_counts": 1100,
            "right_encoder_counts": 1100,
            "bump_left": True,
            "timestamp": "t1",
        }
    )
    assert round(pose["x_mm"], 3) == 0.0
    assert round(pose["y_mm"], 3) == 0.0


def test_bump_blocks_forward_but_keeps_rotation() -> None:
    odom = OdometryEstimator(source="encoders")
    odom.reset(0, 0, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry(
        {
            "left_encoder_counts": 900,
            "right_encoder_counts": 1100,
            "bump_right": True,
            "timestamp": "t1",
        }
    )
    assert round(pose["x_mm"], 3) == 0.0
    assert round(pose["y_mm"], 3) == 0.0
    assert abs(pose["theta_deg"]) > 0.1


def test_encoder_mode_applies_linear_scale() -> None:
    odom_a = OdometryEstimator(source="encoders", linear_scale=1.0)
    odom_b = OdometryEstimator(source="encoders", linear_scale=0.5)
    odom_a.reset(0, 0, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    odom_b.reset(0, 0, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose_a = odom_a.update_from_telemetry({"left_encoder_counts": 1200, "right_encoder_counts": 1200, "timestamp": "t1"})
    pose_b = odom_b.update_from_telemetry({"left_encoder_counts": 1200, "right_encoder_counts": 1200, "timestamp": "t1"})
    assert pose_b["x_mm"] < pose_a["x_mm"]


def test_collision_guard_blocks_motion_when_touching_room_wall() -> None:
    odom = OdometryEstimator(source="encoders")
    odom.set_collision_plan(
        {
            "contour": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]],
            "objects": [],
        },
        robot_radius_mm=100,
    )
    odom.reset(900, 500, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry({"left_encoder_counts": 1200, "right_encoder_counts": 1200, "timestamp": "t1"})
    assert round(pose["x_mm"], 3) == 900.0
    assert round(pose["y_mm"], 3) == 500.0


def test_collision_guard_prevents_crossing_object_polygon() -> None:
    odom = OdometryEstimator(source="encoders")
    odom.set_collision_plan(
        {
            "contour": [[0, 0], [1200, 0], [1200, 1000], [0, 1000]],
            "object_shapes": {
                "block": {
                    "contour": [[0, 0], [200, 0], [200, 200], [0, 200]],
                }
            },
            "objects": [
                {
                    "shape_ref": "block",
                    "x_mm": 500,
                    "y_mm": 400,
                    "theta_deg": 0,
                }
            ],
        },
        robot_radius_mm=80,
    )
    odom.reset(300, 500, 0, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry({"left_encoder_counts": 2000, "right_encoder_counts": 2000, "timestamp": "t1"})
    assert pose["x_mm"] <= 420.0
    assert round(pose["y_mm"], 3) == 500.0


def test_collision_guard_slides_along_wall() -> None:
    odom = OdometryEstimator(source="encoders")
    odom.set_collision_plan(
        {
            "contour": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]],
            "objects": [],
        },
        robot_radius_mm=50,
    )
    odom.reset(200, 940, 45, base_left_encoder_counts=1000, base_right_encoder_counts=1000)
    pose = odom.update_from_telemetry({"left_encoder_counts": 1200, "right_encoder_counts": 1200, "timestamp": "t1"})
    assert pose["x_mm"] > 230.0
    assert pose["y_mm"] <= 951.0
