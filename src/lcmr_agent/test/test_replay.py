from lcmr_agent.agent import Agent
from lcmr_agent.console import Console
from lcmr_agent.evaluation import Case, score
from lcmr_agent.replay import replay
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
