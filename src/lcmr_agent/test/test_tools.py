from lcmr_agent.robot import Pose
from lcmr_agent.tools import ToolBox

from conftest import RecordingRobot

SIX_TOOLS = {
    "list_locations",
    "navigate_to",
    "get_robot_pose",
    "get_navigation_status",
    "cancel_navigation",
    "check_battery",
}


def test_specs_expose_exactly_the_six_tools(toolbox):
    assert {spec["name"] for spec in toolbox.specs()} == SIX_TOOLS
    assert len(toolbox.specs()) == 6


def test_specs_forbid_extra_arguments(toolbox):
    for spec in toolbox.specs():
        assert spec["input_schema"]["additionalProperties"] is False


def test_list_locations_returns_room_names(toolbox):
    result = toolbox.call("list_locations", {})
    assert result.is_error is False
    assert result.content == {"locations": ["dock", "kitchen", "office"]}


def test_navigate_to_known_room_sends_its_stored_pose(toolbox, robot):
    result = toolbox.call("navigate_to", {"location": "kitchen"})
    assert result.is_error is False
    assert result.content["status"] == "succeeded"
    assert robot.goals == [Pose(4.0, 0.0, 1.57)]


def test_navigate_to_accepts_name_in_any_case(toolbox, robot):
    assert toolbox.call("navigate_to", {"location": "Kitchen"}).content["status"] == "succeeded"


def test_navigate_to_unknown_room_is_rejected_before_reaching_robot(toolbox, robot):
    result = toolbox.call("navigate_to", {"location": "garage"})
    assert result.is_error is True
    assert "garage" in result.content["error"]
    assert result.content["known_locations"] == ["dock", "kitchen", "office"]
    assert robot.goals == []


def test_navigate_to_rejects_invented_coordinates(toolbox, robot):
    result = toolbox.call("navigate_to", {"location": "kitchen", "x": 9.0, "y": 9.0})
    assert result.is_error is True
    assert robot.goals == []


def test_navigate_to_rejects_missing_or_wrongly_typed_location(toolbox, robot):
    assert toolbox.call("navigate_to", {}).is_error is True
    assert toolbox.call("navigate_to", {"location": 7}).is_error is True
    assert robot.goals == []


def test_no_argument_tools_reject_arguments(toolbox):
    assert toolbox.call("check_battery", {"percent": 100}).is_error is True


def test_unknown_tool_is_an_error(toolbox, robot):
    result = toolbox.call("set_velocity", {"linear": 1.0})
    assert result.is_error is True
    assert robot.goals == []


def test_failed_navigation_reports_reason(toolbox, robot):
    robot.fail_next("path blocked")
    result = toolbox.call("navigate_to", {"location": "kitchen"})
    assert result.content == {"status": "failed", "location": "kitchen", "reason": "path blocked"}


def test_after_a_failed_step_further_trips_in_the_same_command_are_refused(toolbox, robot):
    robot.fail_next("path blocked")
    toolbox.call("navigate_to", {"location": "kitchen"})
    result = toolbox.call("navigate_to", {"location": "office"})
    assert result.is_error is True
    assert "kitchen" in result.content["error"]
    assert robot.goals == [Pose(4.0, 0.0, 1.57)]


def test_a_new_command_clears_the_stopped_plan(toolbox, robot):
    robot.fail_next("path blocked")
    toolbox.call("navigate_to", {"location": "kitchen"})
    toolbox.begin_command()
    assert toolbox.call("navigate_to", {"location": "office"}).content["status"] == "succeeded"


def test_low_battery_refuses_trips_except_to_the_dock(locations):
    robot = RecordingRobot(start=Pose(4.0, 0.0, 0.0), speed_mps=float("inf"), battery_percent=19.0)
    toolbox = ToolBox(robot, locations)

    refused = toolbox.call("navigate_to", {"location": "office"})
    assert refused.is_error is True
    assert "battery" in refused.content["error"].lower()
    assert robot.goals == []

    assert toolbox.call("navigate_to", {"location": "dock"}).content["status"] == "succeeded"


def test_battery_at_threshold_still_allows_trips(locations):
    robot = RecordingRobot(start=Pose(0, 0, 0), speed_mps=float("inf"), battery_percent=20.0,
                           drain_per_meter=0.0)
    toolbox = ToolBox(robot, locations)
    assert toolbox.call("navigate_to", {"location": "office"}).content["status"] == "succeeded"


def test_get_robot_pose_reports_position_heading_and_nearest_room(toolbox, robot):
    toolbox.call("navigate_to", {"location": "kitchen"})
    result = toolbox.call("get_robot_pose", {})
    assert result.content == {"x": 4.0, "y": 0.0, "heading_deg": 90.0, "nearest_room": "kitchen"}


def test_get_navigation_status_is_idle_at_rest(toolbox):
    assert toolbox.call("get_navigation_status", {}).content == {"status": "idle"}


def test_cancel_navigation_confirms_when_nothing_was_active(toolbox):
    assert toolbox.call("cancel_navigation", {}).content == {
        "cancelled": False, "detail": "No navigation goal was active."}


def test_check_battery_returns_percent(toolbox):
    assert toolbox.call("check_battery", {}).content == {"percent": 100.0}


def test_robot_backend_failure_becomes_a_tool_error_not_a_crash(locations):
    from lcmr_agent.robot import RobotError

    class NoPoseRobot(RecordingRobot):
        def get_pose(self):
            raise RobotError("No pose received from localisation yet.")

    toolbox = ToolBox(NoPoseRobot(), locations)
    result = toolbox.call("get_robot_pose", {})
    assert result.is_error is True
    assert "No pose received" in result.content["error"]
