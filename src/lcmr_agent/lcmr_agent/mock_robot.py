"""A stand-in robot for development and tests without ROS.

It moves in a straight line at a fixed speed, can be cancelled from another
thread, and can be told to fail its next trip.
"""
import math
import threading

from .robot import NavOutcome, NavResult, NavStatus, Pose

_TICK_S = 0.02


class MockRobot:
    def __init__(self, start: Pose = Pose(0.0, 0.0, 0.0), speed_mps: float = 0.5,
                 battery_percent: float = 100.0, drain_per_meter: float = 0.5):
        self._pose = start
        self._speed = speed_mps
        self._battery = battery_percent
        self._drain = drain_per_meter
        self._status = NavStatus.IDLE
        self._next_failure: str | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def fail_next(self, reason: str) -> None:
        """Make the next trip fail with this reason."""
        self._next_failure = reason

    def navigate_to_pose(self, pose: Pose) -> NavResult:
        with self._lock:
            failure, self._next_failure = self._next_failure, None
            if failure is not None:
                self._status = NavStatus.FAILED
                return NavResult(NavOutcome.FAILED, failure)
            self._cancel.clear()
            self._status = NavStatus.NAVIGATING
            start = self._pose

        distance = math.hypot(pose.x - start.x, pose.y - start.y)
        duration = distance / self._speed if distance else 0.0
        elapsed = 0.0
        while elapsed < duration:
            if self._cancel.wait(_TICK_S):
                break
            elapsed = min(elapsed + _TICK_S, duration)
            self._move(start, pose, elapsed / duration)

        with self._lock:
            self._status = NavStatus.IDLE
            cancelled = self._cancel.is_set()
            travelled = distance * (elapsed / duration) if cancelled and duration else distance
            self._battery = max(0.0, self._battery - travelled * self._drain)
            if cancelled:
                return NavResult(NavOutcome.CANCELLED, "cancelled before arrival")
            self._pose = pose
            return NavResult(NavOutcome.SUCCEEDED)

    def cancel_navigation(self) -> bool:
        with self._lock:
            if self._status is not NavStatus.NAVIGATING:
                return False
            self._cancel.set()
            return True

    def get_pose(self) -> Pose:
        with self._lock:
            return self._pose

    def get_navigation_status(self) -> NavStatus:
        with self._lock:
            return self._status

    def get_battery_percent(self) -> float:
        with self._lock:
            return self._battery

    def set_battery_percent(self, percent: float) -> None:
        with self._lock:
            self._battery = percent

    def shutdown(self) -> None:
        """Nothing to release; here so both backends end the same way."""

    def _move(self, start: Pose, goal: Pose, fraction: float) -> None:
        with self._lock:
            self._pose = Pose(start.x + (goal.x - start.x) * fraction,
                              start.y + (goal.y - start.y) * fraction, goal.yaw)
