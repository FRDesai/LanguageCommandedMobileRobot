import sys
import time

from lcmr_agent.agent import Agent
from lcmr_agent.console import Console, main
from lcmr_agent.locations import Locations
from lcmr_agent.mock_robot import MockRobot
from lcmr_agent.robot import NavStatus, Pose
from lcmr_agent.session import Session
from lcmr_agent.tools import ToolBox

from conftest import FakeClient, read_events, response, text, tool_use


def make_console(script, log, tmp_path):
    path = tmp_path / "far.yaml"
    path.write_text("locations:\n  dock: {x: 0, y: 0, yaw: 0}\n  kitchen: {x: 50, y: 0, yaw: 0}\n")
    robot = MockRobot(start=Pose(0, 0, 0), speed_mps=1.0)  # 50 s away: never arrives in a test
    agent = Agent(FakeClient(script), ToolBox(robot, Locations.load(path)), log)
    replies = []
    return Console(Session(agent, robot, log), write=replies.append), robot, replies


def wait_until_navigating(robot):
    deadline = time.monotonic() + 2
    while robot.get_navigation_status() is not NavStatus.NAVIGATING:
        assert time.monotonic() < deadline, "robot never started moving"
        time.sleep(0.005)


def test_stop_typed_mid_trip_cancels_it_while_the_command_is_still_running(log, tmp_path):
    console, robot, replies = make_console(
        [response(tool_use("navigate_to", {"location": "kitchen"})),
         response(text("The trip to the kitchen was cancelled."))],
        log, tmp_path)

    console.submit("Go to the kitchen")
    wait_until_navigating(robot)
    console.submit("stop")
    console.wait()

    assert replies == ["Stopped. Navigation cancelled.", "The trip to the kitchen was cancelled."]
    assert robot.get_pose().x < 50
    [call] = [e for e in read_events(log) if e["event"] == "tool_call"]
    assert call["result"]["status"] == "cancelled"


def test_second_command_while_busy_is_turned_away(log, tmp_path):
    console, robot, replies = make_console(
        [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Cancelled."))],
        log, tmp_path)

    console.submit("Go to the kitchen")
    wait_until_navigating(robot)
    console.submit("Go to the dock")
    assert "still working" in replies[0].lower()

    console.submit("stop")
    console.wait()


def test_blank_input_is_ignored(log, tmp_path):
    console, _, replies = make_console([], log, tmp_path)
    console.submit("   ")
    console.wait()
    assert replies == []


def test_main_shuts_the_robot_down_when_the_user_quits(toolbox, robot, locations, log, monkeypatch):
    session = Session(Agent(FakeClient([]), toolbox, log), robot, log)
    monkeypatch.setattr("lcmr_agent.app.build", lambda args: (session, robot, locations, log))
    monkeypatch.setattr(sys, "argv", ["chat"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "quit")

    main()

    assert robot.shut_down
