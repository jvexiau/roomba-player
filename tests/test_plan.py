from pathlib import Path

from roomba_player.plan import PlanManager


def test_load_yaml_plan(tmp_path: Path) -> None:
    p = tmp_path / "plan.yaml"
    p.write_text(
        """
unit: mm
contour:
  - [0, 0]
  - [1000, 0]
  - [1000, 1000]
start_pose:
  x_mm: 100
  y_mm: 200
  theta_deg: 90
""".strip(),
        encoding="utf-8",
    )
    manager = PlanManager()
    loaded = manager.load_from_file(str(p))
    assert loaded["unit"] == "mm"
    assert len(loaded["contour"]) == 3
