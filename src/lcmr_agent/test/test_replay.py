import sys

from lcmr_agent.agent import Agent
from lcmr_agent.console import Console
from lcmr_agent.evaluation import Case, score
from lcmr_agent.replay import main, replay
from lcmr_agent.session import Session

from conftest import FakeClient, read_events, response, text, tool_use


def make(script, toolbox, robot, log):
    session = Session(Agent(FakeClient(script), toolbox, log), robot, log)
    return Console(session, write=lambda reply: None)


def test_each_case_is_run_the_requested_number_of_times_and_bracketed_in_the_log(toolbox, robot, log):
    cases = {"s1": Case("s1", "single", "Go to the kitchen", {"visits": ["kitchen"]})}
    script = [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Arrived."))] * 2
    replay(cases, make(script, toolbox, robot, log), robot, log, runs=2)

    events = read_events(log)
    assert [(e["case_id"], e["run"]) for e in events if e["event"] == "case_started"] == [("s1", 1), ("s1", 2)]
    report = score(events, cases)
    assert report.counts("single") == (2, 2)


def test_low_battery_case_sets_the_battery_then_restores_it(toolbox, robot, log):
    cases = {"a1": Case("a1", "adversarial", "Go to the kitchen", {"refuse": True}, battery_percent=15.0)}
    script = [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Battery too low."))]
    replay(cases, make(script, toolbox, robot, log), robot, log, runs=1)

    assert robot.goals == []
    assert robot.get_battery_percent() == 100.0
    assert score(read_events(log), cases).counts("adversarial") == (1, 1)


def test_every_case_starts_on_a_full_battery(toolbox, robot, log):
    # Earlier trips drain the battery; without a recharge, later cases would be refused as low-battery.
    robot.set_battery_percent(10.0)
    cases = {"s1": Case("s1", "single", "Go to the kitchen", {"visits": ["kitchen"]})}
    script = [response(tool_use("navigate_to", {"location": "kitchen"})), response(text("Arrived."))]
    replay(cases, make(script, toolbox, robot, log), robot, log, runs=1)

    assert len(robot.goals) == 1
    assert score(read_events(log), cases).counts("single") == (1, 1)


def test_main_shuts_the_robot_down_after_the_replay(toolbox, robot, locations, log, tmp_path, monkeypatch):
    cases = tmp_path / "cases.yaml"
    cases.write_text('cases:\n  - {id: q1, category: question, command: "What rooms do you know?", '
                     'expect: {tool: list_locations}}\n')
    script = [response(tool_use("list_locations")), response(text("Dock, kitchen and office."))]
    session = Session(Agent(FakeClient(script), toolbox, log), robot, log)
    monkeypatch.setattr("lcmr_agent.app.build", lambda args: (session, robot, locations, log))
    monkeypatch.setattr(sys, "argv", ["replay", "--cases", str(cases), "--runs", "1", "--log", str(log.path)])

    main()

    assert robot.shut_down
