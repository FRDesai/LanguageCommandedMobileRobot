"""The only doorway between the agent and the robot.

Nothing in this interface carries a velocity or a motor command: a backend can
be asked to go to a pose, to cancel, and to report state. Motion itself is the
navigation stack's job.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    yaw: float  # radians


class NavOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NavStatus(str, Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    FAILED = "failed"


@dataclass(frozen=True)
class NavResult:
    outcome: NavOutcome
    reason: str = ""


class RobotError(Exception):
    """The backend could not answer, e.g. localisation has not produced a pose yet."""


class Robot(Protocol):
    def navigate_to_pose(self, pose: Pose) -> NavResult:
        """Drive to the pose and block until the trip ends."""

    def cancel_navigation(self) -> bool:
        """Cancel the active goal. Returns False if none was active. Thread-safe."""

    def get_pose(self) -> Pose: ...

    def get_navigation_status(self) -> NavStatus: ...

    def get_battery_percent(self) -> float: ...

    def shutdown(self) -> None:
        """Release the backend. Call once, when the program is ending."""
