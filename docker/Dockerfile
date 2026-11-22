# ROS 2 Humble + TurtleBot3 simulation + Nav2 + SLAM. Built for linux/amd64 (see docker-compose.yml).
# Gazebo runs headless (gzserver only); RViz is viewed in a browser through noVNC.
FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-navigation2 \
      ros-humble-nav2-bringup \
      ros-humble-slam-toolbox \
      ros-humble-turtlebot3-gazebo \
      ros-humble-turtlebot3-navigation2 \
      ros-humble-turtlebot3-cartographer \
      ros-humble-turtlebot3-teleop \
      ros-humble-rviz2 \
      python3-pip \
      xvfb x11vnc novnc websockify fluxbox \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 22.04 ships Pydantic 1; the agent needs Pydantic 2 and the Anthropic SDK.
RUN pip3 install --no-cache-dir "pydantic>=2" anthropic pytest

# The house world's ground, light and furniture come from Gazebo's online model
# database. Fetch them now: without a local copy Gazebo looks them up online at
# every start, and when that server is slow the robot fails to spawn.
RUN apt-get update && apt-get install -y --no-install-recommends xterm curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /root/.gazebo/models \
    && for model in ground_plane sun cafe_table first_2015_trash_can mailbox table_marble; do \
         curl -fsSL "http://models.gazebosim.org/$model/model.tar.gz" | tar xz -C /root/.gazebo/models; \
       done

# burger: lidar only, no camera, so Gazebo needs no GPU rendering.
ENV TURTLEBOT3_MODEL=burger \
    LIBGL_ALWAYS_SOFTWARE=1 \
    DISPLAY=:1

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
WORKDIR /ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
