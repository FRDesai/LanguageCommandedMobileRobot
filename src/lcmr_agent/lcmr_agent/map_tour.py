"""One-off mapping helper: drives the robot through a list of waypoints.

Run it while slam_toolbox and Nav2 are up (mapping.launch.py) so the SLAM map
fills in room by room. It only sends goals; Nav2 does the driving. Not used by
the agent.
"""
import argparse
import threading
import time
from pathlib import Path

import rclpy
import yaml
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import MapMetaData
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

_EDGE_MARGIN_M = 0.3   # stepping-stone goals stay this far inside the map edge
_MAP_SETTLE_S = 15.0   # wall-clock wait for SLAM to publish the larger map
_MAX_STEPS = 8         # stepping-stone goals per waypoint


def _wait(future, timeout_s):
    done = threading.Event()
    future.add_done_callback(lambda _: done.set())
    return future.result() if done.wait(timeout_s) else None


class Tour(Node):
    def __init__(self):
        super().__init__("lcmr_map_tour")
        self.nav = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._map_info = None
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(MapMetaData, "map_metadata", self._on_map_info, latched)

    def _on_map_info(self, msg: MapMetaData) -> None:
        self._map_info = msg

    def _inside_map(self, x: float, y: float) -> tuple[float, float]:
        """The nearest point to (x, y) that is inside the map built so far."""
        info = self._map_info
        if info is None:
            return x, y
        low_x = info.origin.position.x + _EDGE_MARGIN_M
        low_y = info.origin.position.y + _EDGE_MARGIN_M
        high_x = info.origin.position.x + info.width * info.resolution - _EDGE_MARGIN_M
        high_y = info.origin.position.y + info.height * info.resolution - _EDGE_MARGIN_M
        return min(max(x, low_x), high_x), min(max(y, low_y), high_y)

    def drive_to(self, x: float, y: float, timeout_s: float) -> bool:
        """Drive to a waypoint, which may lie beyond the map built so far.

        Nav2 rejects goals outside the map, so head for the nearest point
        inside it, let SLAM extend the map from there, and try again.
        """
        for _ in range(_MAX_STEPS):
            step = self._inside_map(x, y)
            reached = self._send_goal(*step, timeout_s)
            if step == (x, y):
                return reached
            self.get_logger().info(
                f"  ({x}, {y}) is beyond the map; went towards ({step[0]:.2f}, {step[1]:.2f})")
            time.sleep(_MAP_SETTLE_S)
            if self._inside_map(x, y) == step:  # the map did not grow
                return False
        return False

    def _send_goal(self, x: float, y: float, timeout_s: float) -> bool:
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.w = 1.0

        handle = _wait(self.nav.send_goal_async(goal), 20.0)
        if handle is None or not handle.accepted:
            return False
        result = _wait(handle.get_result_async(), timeout_s)
        if result is None:
            _wait(handle.cancel_goal_async(), 10.0)
            return False
        return result.status == GoalStatus.STATUS_SUCCEEDED


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive through waypoints to build the SLAM map.")
    parser.add_argument("waypoints", help="YAML file with a 'waypoints' list of [x, y]")
    parser.add_argument("--goal-timeout", type=float, default=300.0, help="wall-clock seconds per waypoint")
    args, _ = parser.parse_known_args()  # leave --ros-args for rclpy
    waypoints = yaml.safe_load(Path(args.waypoints).read_text())["waypoints"]

    rclpy.init()
    node = Tour()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    node.nav.wait_for_server()

    missed = 0
    for number, (x, y) in enumerate(waypoints, start=1):
        reached = node.drive_to(float(x), float(y), args.goal_timeout)
        missed += not reached
        node.get_logger().info(
            f"Waypoint {number}/{len(waypoints)} ({x}, {y}): {'reached' if reached else 'NOT reached'}")
    node.get_logger().info(f"Tour finished; {missed} waypoint(s) not reached.")
    executor.shutdown()


if __name__ == "__main__":
    main()
