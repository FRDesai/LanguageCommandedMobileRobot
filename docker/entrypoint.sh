#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.sh
[ -f /ws/install/setup.bash ] && source /ws/install/setup.bash

# Virtual display served to the browser at http://localhost:6080/vnc.html
Xvfb :1 -screen 0 1280x800x24 >/dev/null 2>&1 &
fluxbox >/dev/null 2>&1 &
x11vnc -display :1 -forever -shared -nopw -quiet >/dev/null 2>&1 &
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &

exec "$@"
