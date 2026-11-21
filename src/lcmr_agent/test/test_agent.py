import json

import anthropic
import httpx2

from lcmr_agent.agent import Agent
from lcmr_agent.robot import Pose

from conftest import FakeClient, read_events, response, text, tool_use

KITCHEN = Pose(4.0, 0.0, 1.57)
OFFICE = Pose(0.0, 3.0, 3.14)
DOCK = Pose(0.0, 0.0, 0.0)


def make_agent(script, toolbox, log, **kwargs):
    client = FakeClient(script)
    return Agent(client, toolbox, log, **kwargs), client


def tool_results(request):
    """The tool_result blocks the agent sent back in a request's last message."""
    return request["messages"][-1]["content"]


def test_single_step_command_drives_to_the_room_and_returns_the_reply(toolbox, robot, log):
    agent, _ = make_agent(
        [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Arrived at the kitchen."))],
        toolbox, log)

    assert agent.run("Go to the kitchen", command_id="c1") == "Arrived at the kitchen."
    assert robot.goals == [KITCHEN]


def test_tool_result_is_returned_to_the_model_with_matching_id(toolbox, log):
    agent, client = make_agent(
        [response(tool_use("navigate_to", {"location": "kitchen"}, block_id="tu_42")), response(text("Done."))],
        toolbox, log)
    agent.run("Go to the kitchen", command_id="c1")

    [result] = tool_results(client.requests[1])
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_42"
    assert result["is_error"] is False
    assert json.loads(result["content"])["status"] == "succeeded"


def test_model_is_offered_only_the_six_tools(toolbox, log):
    agent, client = make_agent([response(text("Hi."))], toolbox, log)
    agent.run("hello", command_id="c1")
    assert len(client.requests[0]["tools"]) == 6


def test_multi_step_command_visits_rooms_in_order(toolbox, robot, log):
    agent, _ = make_agent(
        [response(tool_use("navigate_to", {"location": "office"})),
         response(tool_use("navigate_to", {"location": "dock"})),
         response(text("Checked the office and returned to the dock."))],
        toolbox, log)
    agent.run("Check the office, then come back to the dock", command_id="c1")
    assert robot.goals == [OFFICE, DOCK]


def test_two_trips_requested_in_one_turn_run_in_order_and_answer_together(toolbox, robot, log):
    agent, client = make_agent(
        [response(tool_use("navigate_to", {"location": "office"}, block_id="a"),
                  tool_use("navigate_to", {"location": "dock"}, block_id="b")),
         response(text("Done."))],
        toolbox, log)
    agent.run("Check the office, then come back to the dock", command_id="c1")

    assert robot.goals == [OFFICE, DOCK]
    assert [r["tool_use_id"] for r in tool_results(client.requests[1])] == ["a", "b"]


def test_when_a_step_fails_later_steps_do_not_move_the_robot(toolbox, robot, log):
    robot.fail_next("path blocked")
    agent, client = make_agent(
        [response(tool_use("navigate_to", {"location": "kitchen"})),
         response(tool_use("navigate_to", {"location": "office"})),
         response(text("I could not reach the kitchen: path blocked."))],
        toolbox, log)
    agent.run("Go to the kitchen then the office", command_id="c1")

    assert robot.goals == [KITCHEN]
    [second] = tool_results(client.requests[2])
    assert second["is_error"] is True


def test_invalid_tool_arguments_come_back_as_an_error_and_never_reach_the_robot(toolbox, robot, log):
    agent, client = make_agent(
        [response(tool_use("navigate_to", {"location": "garage"})),
         response(text("I don't know a garage."))],
        toolbox, log)
    agent.run("Go to the garage", command_id="c1")

    assert robot.goals == []
    assert tool_results(client.requests[1])[0]["is_error"] is True


def test_each_command_starts_with_a_fresh_plan(toolbox, robot, log):
    robot.fail_next("path blocked")
    agent, _ = make_agent(
        [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Failed.")),
         response(tool_use("navigate_to", {"location": "office"})), response(text("At the office."))],
        toolbox, log)
    agent.run("Go to the kitchen", command_id="c1")
    agent.run("Go to the office", command_id="c2")
    assert robot.goals == [KITCHEN, OFFICE]


def test_model_refusal_is_reported_without_moving(toolbox, robot, log):
    agent, _ = make_agent([response(stop_reason="refusal")], toolbox, log)
    reply = agent.run("something disallowed", command_id="c1")
    assert "declined" in reply.lower()
    assert robot.goals == []


def test_runaway_tool_loop_is_cut_off(toolbox, log):
    script = [response(tool_use("check_battery")) for _ in range(5)]
    agent, client = make_agent(script, toolbox, log, max_turns=3)
    reply = agent.run("loop forever", command_id="c1")
    assert len(client.requests) == 3
    assert "too many steps" in reply.lower()


def test_api_connection_failure_gives_a_plain_message(toolbox, robot, log):
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    agent, _ = make_agent([error], toolbox, log)
    reply = agent.run("Go to the kitchen", command_id="c1")
    assert "could not reach" in reply.lower()
    assert robot.goals == []


def test_every_tool_call_is_logged_with_result_and_timing(toolbox, log):
    agent, _ = make_agent(
        [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Arrived."))],
        toolbox, log)
    agent.run("Go to the kitchen", command_id="c7")

    [call] = [e for e in read_events(log) if e["event"] == "tool_call"]
    assert call["command_id"] == "c7"
    assert call["tool"] == "navigate_to"
    assert call["input"] == {"location": "kitchen"}
    assert call["is_error"] is False
    assert call["result"]["status"] == "succeeded"
    assert call["duration_s"] >= 0
    assert call["started_ts"] > 0
