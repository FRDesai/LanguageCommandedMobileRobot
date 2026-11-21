import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Make the package importable without installing it (works on any pytest version).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lcmr_agent.event_log import EventLog
from lcmr_agent.locations import Locations
from lcmr_agent.mock_robot import MockRobot
from lcmr_agent.robot import Pose
from lcmr_agent.tools import ToolBox

LOCATIONS_YAML = """
locations:
  dock: {x: 0.0, y: 0.0, yaw: 0.0}
  kitchen: {x: 4.0, y: 0.0, yaw: 1.57}
  office: {x: 0.0, y: 3.0, yaw: 3.14}
"""


class RecordingRobot(MockRobot):
    """MockRobot that remembers every goal it was asked to drive to."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.goals = []

    def navigate_to_pose(self, pose):
        self.goals.append(pose)
        return super().navigate_to_pose(pose)


@pytest.fixture
def locations(tmp_path):
    path = tmp_path / "locations.yaml"
    path.write_text(LOCATIONS_YAML)
    return Locations.load(path)


@pytest.fixture
def robot():
    # Instant motion so tests do not sleep.
    return RecordingRobot(start=Pose(0.0, 0.0, 0.0), speed_mps=float("inf"))


@pytest.fixture
def toolbox(robot, locations):
    return ToolBox(robot, locations)


@pytest.fixture
def log(tmp_path):
    return EventLog(tmp_path / "events.jsonl")


def read_events(log):
    return [json.loads(line) for line in log.path.read_text().splitlines()]


# --- scripted stand-in for the Anthropic client -----------------------------

def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(name, tool_input=None, block_id=None):
    return SimpleNamespace(
        type="tool_use", id=block_id or f"tu_{name}", name=name, input=tool_input or {}
    )


def response(*blocks, stop_reason=None):
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, stop_details=None)


class FakeClient:
    """Replays scripted responses and records each request it receives."""

    def __init__(self, script):
        self._script = list(script)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
