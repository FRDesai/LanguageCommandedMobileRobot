"""Simulation + SLAM + Nav2, for building the map (no AMCL, no saved map)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    here = os.path.join(get_package_share_directory("lcmr_agent"), "launch")
    nav2_params = os.path.join(get_package_share_directory("turtlebot3_navigation2"),
                               "param", "humble", os.environ["TURTLEBOT3_MODEL"] + ".yaml")

    def include(package_dir, *path, **arguments):
        return IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(package_dir, *path)),
            launch_arguments=arguments.items())

    return LaunchDescription([
        include(here, "sim.launch.py"),
        include(get_package_share_directory("slam_toolbox"), "launch", "online_async_launch.py",
                use_sim_time="true"),
        include(get_package_share_directory("nav2_bringup"), "launch", "navigation_launch.py",
                use_sim_time="true", params_file=nav2_params),
    ])
