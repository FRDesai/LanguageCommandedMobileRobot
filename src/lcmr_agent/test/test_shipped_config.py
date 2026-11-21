"""Checks on the config files that ship with the package."""
from collections import Counter
from pathlib import Path

from lcmr_agent.evaluation import load_cases
from lcmr_agent.locations import Locations
from lcmr_agent.safety import is_stop_command

CONFIG = Path(__file__).resolve().parent.parent / "config"


def test_test_set_has_the_30_commands_the_prd_asks_for():
    cases = load_cases(CONFIG / "test_set.yaml")
    assert Counter(c.category for c in cases.values()) == {
        "single": 12, "multi": 8, "question": 5, "adversarial": 5}


def test_test_set_only_expects_rooms_that_exist():
    rooms = set(Locations.load(CONFIG / "locations.yaml").names())
    for case in load_cases(CONFIG / "test_set.yaml").values():
        named = case.expect.get("visits", []) + case.expect.get("allowed", [])
        assert set(named) <= rooms, case.id


def test_every_room_has_a_single_step_command():
    rooms = set(Locations.load(CONFIG / "locations.yaml").names())
    visited = {room for case in load_cases(CONFIG / "test_set.yaml").values()
               if case.category == "single" for room in case.expect["visits"]}
    assert visited == rooms


def test_no_test_command_trips_the_stop_filter_by_accident():
    for case in load_cases(CONFIG / "test_set.yaml").values():
        assert not is_stop_command(case.command), case.id
