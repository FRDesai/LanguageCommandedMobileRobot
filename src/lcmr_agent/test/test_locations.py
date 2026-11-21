import pytest

from lcmr_agent.locations import Locations
from lcmr_agent.robot import Pose


def test_load_reads_named_poses(locations):
    assert locations.names() == ["dock", "kitchen", "office"]
    assert locations.get("kitchen") == Pose(4.0, 0.0, 1.57)


def test_get_ignores_case_and_surrounding_spaces(locations):
    assert locations.get("  Kitchen ") == Pose(4.0, 0.0, 1.57)


def test_get_unknown_name_returns_none(locations):
    assert locations.get("garage") is None


def test_nearest_returns_closest_room(locations):
    assert locations.nearest(3.5, 0.4) == "kitchen"


def test_load_rejects_entry_missing_a_coordinate(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("locations:\n  kitchen: {x: 1.0, yaw: 0.0}\n")
    with pytest.raises(ValueError, match="kitchen"):
        Locations.load(path)


def test_load_rejects_file_with_no_locations(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("locations: {}\n")
    with pytest.raises(ValueError, match="no locations"):
        Locations.load(path)
