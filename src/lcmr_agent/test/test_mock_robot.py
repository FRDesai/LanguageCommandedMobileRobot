import threading
import time

from lcmr_agent.mock_robot import MockRobot
from lcmr_agent.robot import NavOutcome, NavStatus, Pose

FAST = float("inf")


def test_navigation_succeeds_and_robot_ends_at_goal():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=FAST)
    result = robot.navigate_to_pose(Pose(2.0, 1.0, 0.5))
    assert result.outcome is NavOutcome.SUCCEEDED
    assert robot.get_pose() == Pose(2.0, 1.0, 0.5)
    assert robot.get_navigation_status() is NavStatus.IDLE


def test_injected_failure_reports_reason_and_failed_status():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=FAST)
    robot.fail_next("path blocked")
    result = robot.navigate_to_pose(Pose(2.0, 0.0, 0.0))
    assert result.outcome is NavOutcome.FAILED
    assert result.reason == "path blocked"
    assert robot.get_pose() == Pose(0, 0, 0)
    assert robot.get_navigation_status() is NavStatus.FAILED


def test_injected_failure_applies_to_one_goal_only():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=FAST)
    robot.fail_next("path blocked")
    robot.navigate_to_pose(Pose(2.0, 0.0, 0.0))
    assert robot.navigate_to_pose(Pose(2.0, 0.0, 0.0)).outcome is NavOutcome.SUCCEEDED


def test_cancel_from_another_thread_stops_the_trip_part_way():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=1.0)
    results = []
    trip = threading.Thread(target=lambda: results.append(robot.navigate_to_pose(Pose(50.0, 0, 0))))
    trip.start()
    deadline = time.monotonic() + 2
    while robot.get_navigation_status() is not NavStatus.NAVIGATING:
        assert time.monotonic() < deadline
        time.sleep(0.005)

    assert robot.cancel_navigation() is True
    trip.join(timeout=2)

    assert results[0].outcome is NavOutcome.CANCELLED
    assert 0 <= robot.get_pose().x < 50.0
    assert robot.get_navigation_status() is NavStatus.IDLE


def test_cancel_with_no_active_goal_reports_nothing_to_cancel():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=FAST)
    assert robot.cancel_navigation() is False


def test_battery_drains_with_distance_travelled():
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=FAST, battery_percent=50.0, drain_per_meter=2.0)
    robot.navigate_to_pose(Pose(3.0, 4.0, 0.0))  # 5 m
    assert robot.get_battery_percent() == 40.0
