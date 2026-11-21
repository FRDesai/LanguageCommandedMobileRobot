"""The six tools. Everything the LLM can do to the robot goes through here.

Safety rules live in this file as code, so they hold whatever the model says:
goals come only from the named-locations file, arguments are schema-checked
before any robot call, a failed step stops the rest of the plan, and a low
battery allows only the trip to the dock.
"""
import math
from dataclasses import dataclass

from pydantic import ValidationError

from .locations import Locations
from .robot import NavOutcome, Robot, RobotError
from .schemas import NavigateToArgs, NoArgs

LOW_BATTERY_PERCENT = 20.0
DOCK = "dock"

_NO_ARGS_SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


@dataclass(frozen=True)
class ToolResult:
    content: dict
    is_error: bool = False


def _error(message: str, **extra) -> ToolResult:
    return ToolResult({"error": message, **extra}, is_error=True)


class ToolBox:
    def __init__(self, robot: Robot, locations: Locations):
        self._robot = robot
        self._locations = locations
        self._stopped_plan: str | None = None
        self._handlers = {
            "list_locations": (NoArgs, self._list_locations),
            "navigate_to": (NavigateToArgs, self._navigate_to),
            "get_robot_pose": (NoArgs, self._get_robot_pose),
            "get_navigation_status": (NoArgs, self._get_navigation_status),
            "cancel_navigation": (NoArgs, self._cancel_navigation),
            "check_battery": (NoArgs, self._check_battery),
        }

    def begin_command(self) -> None:
        """Start a new user command: a plan stopped by an earlier failure no longer applies."""
        self._stopped_plan = None

    def call(self, name: str, raw_input: dict) -> ToolResult:
        if name not in self._handlers:
            return _error(f"Unknown tool '{name}'.", known_tools=list(self._handlers))
        schema, handler = self._handlers[name]
        try:
            args = schema.model_validate(raw_input)
        except ValidationError as error:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in error.errors())
            return _error(f"Invalid arguments for {name}: {problems}")
        try:
            return handler(args)
        except RobotError as error:
            return _error(str(error))

    def specs(self) -> list[dict]:
        """Tool definitions in the Anthropic Messages API format."""
        def spec(name, description, input_schema=_NO_ARGS_SCHEMA):
            return {"name": name, "description": description, "strict": True,
                    "input_schema": input_schema}

        return [
            spec("list_locations",
                 "List the names of every room the robot can be sent to. These are the only "
                 "valid destinations."),
            spec("navigate_to",
                 "Drive the robot to a named room and wait until the trip ends. Returns "
                 "status succeeded, failed or cancelled, with a reason. Call it once per room, "
                 "one room at a time, in the order the user asked. If a trip does not succeed, "
                 "stop and report it; further trips in the same command are refused.",
                 {"type": "object",
                  "properties": {"location": {
                      "type": "string", "enum": self._locations.names(),
                      "description": "Name of a known room."}},
                  "required": ["location"], "additionalProperties": False}),
            spec("get_robot_pose",
                 "Get the robot's current position (x, y in metres), heading in degrees, and "
                 "the nearest named room. Use it to answer where the robot is."),
            spec("get_navigation_status",
                 "Report whether the robot is idle, navigating, or its last trip failed."),
            spec("cancel_navigation", "Cancel the trip in progress so the robot stops."),
            spec("check_battery", "Get the battery level as a percentage."),
        ]

    # --- handlers ---------------------------------------------------------

    def _list_locations(self, _args) -> ToolResult:
        return ToolResult({"locations": self._locations.names()})

    def _navigate_to(self, args: NavigateToArgs) -> ToolResult:
        name = args.location.strip().lower()
        pose = self._locations.get(name)
        if pose is None:
            return _error(f"Unknown location '{args.location}'. The robot did not move.",
                          known_locations=self._locations.names())
        if self._stopped_plan is not None:
            return _error(f"Plan stopped: {self._stopped_plan} No further trips will run for "
                          "this command. Tell the user which step failed and why.")
        battery = self._robot.get_battery_percent()
        if battery < LOW_BATTERY_PERCENT and name != DOCK:
            return _error(f"Battery is at {battery:.0f}%, below {LOW_BATTERY_PERCENT:.0f}%. "
                          f"Only a trip to the {DOCK} is allowed. The robot did not move.")

        result = self._robot.navigate_to_pose(pose)
        if result.outcome is not NavOutcome.SUCCEEDED:
            self._stopped_plan = (
                f"the trip to '{name}' {result.outcome.value} ({result.reason or 'no reason given'}).")
        return ToolResult({"status": result.outcome.value, "location": name, "reason": result.reason})

    def _get_robot_pose(self, _args) -> ToolResult:
        pose = self._robot.get_pose()
        return ToolResult({
            "x": round(pose.x, 2), "y": round(pose.y, 2),
            "heading_deg": round(math.degrees(pose.yaw), 1),
            "nearest_room": self._locations.nearest(pose.x, pose.y)})

    def _get_navigation_status(self, _args) -> ToolResult:
        return ToolResult({"status": self._robot.get_navigation_status().value})

    def _cancel_navigation(self, _args) -> ToolResult:
        cancelled = self._robot.cancel_navigation()
        detail = "Navigation cancelled." if cancelled else "No navigation goal was active."
        return ToolResult({"cancelled": cancelled, "detail": detail})

    def _check_battery(self, _args) -> ToolResult:
        return ToolResult({"percent": round(self._robot.get_battery_percent(), 1)})
