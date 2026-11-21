"""Robot backend for ROS 2: goals go to Nav2, pose comes from AMCL.

This node creates one action client (NavigateToPose) and two subscriptions. It
has no publishers of its own, so it cannot send velocity or motor commands;
only Nav2 drives the robot.
"""
import math
import threading

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from .robot import NavOutcome, NavResult, NavStatus, Pose, RobotError

_SERVER_TIMEOUT_S = 10.0
_ACCEPT_TIMEOUT_S = 10.0


def _yaw_from_quaternion(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class RosRobot:
    def __init__(self, initial_battery_percent: float = 100.0, drain_per_meter: float = 0.5):
        if not rclpy.ok():
            rclpy.init()
        self._node = Node("lcmr_agent")
        self._nav = ActionClient(self._node, NavigateToPose, "navigate_to_pose")

        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._node.create_subscription(PoseWithCovarianceStamped, "amcl_pose", self._on_amcl, latched)
        self._node.create_subscription(Odometry, "odom", self._on_odom, 10)

        self._lock = threading.Lock()
        self._pose: Pose | None = None
        self._status = NavStatus.IDLE
        self._goal_handle = None
        self._cancel_requested = False
        # Simulated battery: drains with distance driven, measured from odometry.
        self._battery = initial_battery_percent
        self._drain = drain_per_meter
        self._last_odom_xy: tuple[float, float] | None = None

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin.start()

    # --- Robot interface ----------------------------------------------------

    def navigate_to_pose(self, pose: Pose) -> NavResult:
        if not self._nav.wait_for_server(timeout_sec=_SERVER_TIMEOUT_S):
            return self._finish(NavStatus.FAILED, NavOutcome.FAILED, "Nav2 is not running.")

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x = pose.x
        goal.pose.pose.position.y = pose.y
        goal.pose.pose.orientation.z = math.sin(pose.yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(pose.yaw / 2.0)

        with self._lock:
            self._cancel_requested = False
            self._status = NavStatus.NAVIGATING

        handle = self._wait(self._nav.send_goal_async(goal), _ACCEPT_TIMEOUT_S)
        if handle is None or not handle.accepted:
            return self._finish(NavStatus.FAILED, NavOutcome.FAILED, "Nav2 rejected the goal.")

        with self._lock:
            self._goal_handle = handle
            cancel_now = self._cancel_requested
        if cancel_now:  # stop arrived while the goal was being accepted
            handle.cancel_goal_async()

        result = self._wait(handle.get_result_async(), None)
        with self._lock:
            self._goal_handle = None

        if result.status == GoalStatus.STATUS_SUCCEEDED:
            return self._finish(NavStatus.IDLE, NavOutcome.SUCCEEDED, "")
        if result.status == GoalStatus.STATUS_CANCELED:
            return self._finish(NavStatus.IDLE, NavOutcome.CANCELLED, "cancelled before arrival")
        return self._finish(NavStatus.FAILED, NavOutcome.FAILED,
                            "Nav2 aborted the trip: no valid path, or the way was blocked.")

    def cancel_navigation(self) -> bool:
        with self._lock:
            if self._status is not NavStatus.NAVIGATING:
                return False
            self._cancel_requested = True
            handle = self._goal_handle
        if handle is not None:
            handle.cancel_goal_async()
        return True

    def get_pose(self) -> Pose:
        with self._lock:
            if self._pose is None:
                raise RobotError("No pose received from localisation (AMCL) yet.")
            return self._pose

    def get_navigation_status(self) -> NavStatus:
        with self._lock:
            return self._status

    def get_battery_percent(self) -> float:
        with self._lock:
            return self._battery

    def set_battery_percent(self, percent: float) -> None:
        """Set the simulated battery level (used by the test replay)."""
        with self._lock:
            self._battery = percent

    def shutdown(self) -> None:
        self._executor.shutdown()
        self._node.destroy_node()

    # --- internals ----------------------------------------------------------

    def _finish(self, status: NavStatus, outcome: NavOutcome, reason: str) -> NavResult:
        with self._lock:
            self._status = status
        return NavResult(outcome, reason)

    @staticmethod
    def _wait(future, timeout_s):
        """Block the calling thread until a future resolved by the spin thread is done."""
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(timeout_s):
            return None
        return future.result()

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        p = msg.pose.pose
        with self._lock:
            self._pose = Pose(p.position.x, p.position.y, _yaw_from_quaternion(p.orientation))

    def _on_odom(self, msg: Odometry) -> None:
        xy = (msg.pose.pose.position.x, msg.pose.pose.position.y)
        with self._lock:
            if self._last_odom_xy is not None:
                step = math.hypot(xy[0] - self._last_odom_xy[0], xy[1] - self._last_odom_xy[1])
                self._battery = max(0.0, self._battery - step * self._drain)
            self._last_odom_xy = xy
