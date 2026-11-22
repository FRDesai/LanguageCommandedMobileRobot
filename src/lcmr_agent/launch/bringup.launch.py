"""Everything for a demo: headless Gazebo, Nav2 on the saved map, RViz and the chat.

RViz and the chat window open on the container's virtual display; view them at
http://localhost:6080/vnc.html
"""
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from lcmr_agent.nav2_params import merge


# Must match the spawn pose in sim.launch.py.
SPAWN_X = -3.5
SPAWN_Y = 1.0


def _nav2_params(changes_path: str) -> str:
    """TurtleBot3's stock Nav2 parameters, plus AMCL's starting pose and this project's changes.

    The map uses the Gazebo world's coordinates, so the robot starts where
    sim.launch.py spawns it. The only other differences from the stock file
    are the ones listed in config/nav2_changes.yaml.
    """
    stock = os.path.join(get_package_share_directory("turtlebot3_navigation2"),
                         "param", "humble", os.environ["TURTLEBOT3_MODEL"] + ".yaml")
    with open(stock) as file:
        params = yaml.safe_load(file)
    with open(changes_path) as file:
        params = merge(params, yaml.safe_load(file) or {})
    params["amcl"]["ros__parameters"].update(
        set_initial_pose=True, initial_pose={"x": SPAWN_X, "y": SPAWN_Y, "z": 0.0, "yaw": 0.0})
    out = tempfile.NamedTemporaryFile("w", suffix=".yaml", prefix="lcmr_nav2_", delete=False)
    yaml.safe_dump(params, out)
    out.close()
    return out.name


def _launch(context):
    share = get_package_share_directory("lcmr_agent")
    nav2_bringup = get_package_share_directory("nav2_bringup")

    def include(package_dir, *path, condition=None, **arguments):
        return IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(package_dir, *path)),
            launch_arguments=arguments.items(), condition=condition)

    return [
        include(share, "launch", "sim.launch.py"),
        include(nav2_bringup, "launch", "bringup_launch.py",
                map=LaunchConfiguration("map"), use_sim_time="true",
                params_file=_nav2_params(LaunchConfiguration("nav2_changes").perform(context))),
        include(nav2_bringup, "launch", "rviz_launch.py",
                condition=IfCondition(LaunchConfiguration("rviz")), use_sim_time="true"),
        Node(package="lcmr_agent", executable="chat", arguments=["--backend", "ros"],
             prefix="xterm -fa Monospace -fs 12 -geometry 100x24 -e", output="screen",
             condition=IfCondition(LaunchConfiguration("chat"))),
    ]


def generate_launch_description():
    share = get_package_share_directory("lcmr_agent")
    default_map = os.path.join(share, "maps", "house.yaml")
    default_changes = os.path.join(share, "config", "nav2_changes.yaml")
    return LaunchDescription([
        DeclareLaunchArgument("map", default_value=default_map, description="saved SLAM map"),
        DeclareLaunchArgument("nav2_changes", default_value=default_changes,
                              description="changes applied on top of the stock Nav2 parameters"),
        DeclareLaunchArgument("rviz", default_value="true", description="open RViz"),
        DeclareLaunchArgument("chat", default_value="true",
                              description="open the chat window (needs ANTHROPIC_API_KEY)"),
        OpaqueFunction(function=_launch),
    ])
