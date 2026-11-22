"""Headless Gazebo with the TurtleBot3 house world and one robot.

Same as turtlebot3_gazebo's turtlebot3_house.launch.py, minus the Gazebo GUI
(gzclient), which is too heavy for an emulated container. View the robot in
RViz instead.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

# Where the robot is spawned in the Gazebo world. Gazebo's odometry starts at
# this world position, so the SLAM map shares the world's coordinates and this
# is also AMCL's starting pose (see bringup.launch.py).
SPAWN_X = "-3.5"
SPAWN_Y = "1.0"


def generate_launch_description():
    tb3_gazebo = get_package_share_directory("turtlebot3_gazebo")
    tb3_launch = os.path.join(tb3_gazebo, "launch")
    gazebo_ros = get_package_share_directory("gazebo_ros")

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(gazebo_ros, "launch", "gzserver.launch.py")),
            launch_arguments={
                "world": os.path.join(tb3_gazebo, "worlds", "turtlebot3_house.world")}.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(tb3_launch, "robot_state_publisher.launch.py")),
            launch_arguments={"use_sim_time": "true"}.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(tb3_launch, "spawn_turtlebot3.launch.py")),
            launch_arguments={"x_pose": SPAWN_X, "y_pose": SPAWN_Y}.items()),
    ])
