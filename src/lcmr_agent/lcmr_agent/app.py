"""Wires the pieces together for the command-line programs."""
import argparse
from pathlib import Path

from .agent import DEFAULT_MODEL, Agent
from .event_log import EventLog
from .locations import Locations
from .session import Session
from .tools import ToolBox


def default_locations_path() -> Path:
    """The installed config when run from a colcon workspace, else the source tree's."""
    try:
        from ament_index_python.packages import get_package_share_directory
        return Path(get_package_share_directory("lcmr_agent")) / "config" / "locations.yaml"
    except Exception:  # not installed, or not running under ROS
        return Path(__file__).resolve().parent.parent / "config" / "locations.yaml"


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", choices=["mock", "ros"], default="mock",
                        help="mock: built-in fake robot; ros: Nav2 through ROS 2")
    parser.add_argument("--locations", default=None, help="named-locations YAML file")
    parser.add_argument("--log", default="logs/events.jsonl", help="JSON-lines event log")
    parser.add_argument("--model", default=DEFAULT_MODEL)


def build(args):
    """Returns (session, robot, locations, log) for the chosen backend."""
    import anthropic

    locations = Locations.load(args.locations or default_locations_path())
    if args.backend == "ros":
        from .ros_robot import RosRobot
        robot = RosRobot()
    else:
        from .mock_robot import MockRobot
        robot = MockRobot(start=locations.get("dock") or locations.get(locations.names()[0]))
    log = EventLog(args.log)
    agent = Agent(anthropic.Anthropic(), ToolBox(robot, locations), log, model=args.model)
    return Session(agent, robot, log), robot, locations, log
