# Language-Commanded Mobile Robot

A simulated TurtleBot3 (ROS 2 Humble, Gazebo, Nav2) that carries out plain-English commands such as
"check the office, then come back to the dock". An LLM agent chooses where the robot goes through six
typed tools; Nav2 alone decides how it moves. The agent never publishes velocities and can only send
the robot to rooms named in `src/lcmr_agent/config/locations.yaml`.

## Results

The test set is 30 fixed commands (12 single-step, 8 multi-step, 5 questions, 5 adversarial), replayed
three times against the full stack: 90 commands in all. The run below used Claude Haiku 5.5, the indoor
dock and the one Nav2 parameter change described further down. It took 2 h 47 min with the simulator
at about half real-time.

| Metric | Target | Result |
| --- | --- | --- |
| Single-step commands completed | ≥ 90% | 100% (36/36) |
| Multi-step commands fully completed | ≥ 80% | 96% (23/24) |
| Questions answered with the right tool | n/a | 100% (15/15) |
| Unsafe or impossible commands correctly refused | 100% | 100% (15/15) |
| "Stop" to cancel request sent | < 1 s | 0.01 s (worst case) |
| Command to navigation goal sent | < 3 s | 2.34 s (worst case) |

- **Trips:** the agent asked for 95 trips. The low-battery rule refused 3 before anything was sent to
  Nav2, as the test intends. Of the 92 sent, 88 reached the room, 3 were cancelled on purpose by the
  "stop" test, and 1 failed.
- **The one failure:** in "Patrol the kitchen, then the bedroom" (second replay), Nav2 aborted the trip
  from the hall to the kitchen after 53 s. The robot was not stuck. Nav2's process paused for about a
  second, its request for a fresh path timed out, and its recovery steps timed out in turn. The agent
  reported the failure and did not go on to the bedroom, which is the intended behaviour. The log shows
  the same one-second pause every ten minutes throughout the run. Its source has not been found; the
  regular interval points at the Docker environment, not at the robot software.
- **Stop time:** the table gives the time to send the cancel request. Nav2's controller logged
  "Stopping the robot" within 0.11 s of each of the three stops. The time for the robot to come to
  rest was not measured.
- **Progress warnings:** Nav2 reported "Failed to make progress" 5 times in the 92 trips, each in the
  last few seconds before arrival. Nav2 retried on its own and all 5 trips reached the room. The cause
  has not been investigated.
- **Log:** `logs/run1_indoor_dock/` (kept locally; the `logs/` folder is not committed).

### Known issue: localisation on the porch

The first test run was stopped early because of where the dock was, and its numbers are not reported.

- **Setup:** the dock, which is also where the robot starts, was on the front porch at (-2.0, -0.5),
  outside the house.
- **Symptom:** of the 17 commands completed before the run was stopped, two failed with the robot
  stuck at the front door, on trips that started from the dock.
- **Cause:** on the porch the lidar (3.5 m range) sees little besides one straight wall, so AMCL's
  position estimate can slide along that wall. Measured while the robot was stuck, the estimate was
  about 0.4 m from the robot's true position in Gazebo, enough to aim it at the door frame instead of
  the opening.
- **Fix:** the dock and start pose were moved indoors, to the living room at (-3.5, 1.0). No Nav2 or AMCL
  parameter was changed for this fix. Over 21 trips of about 220 m in total with the new
  dock, the estimate stayed within 0.28 m of the true position.
- **Log:** the stopped run's log is kept locally as `logs/run0_porch_dock/` (the `logs/` folder is not
  committed).

A robot that has to dock outdoors would need more for the lidar to see near the dock, or a different
localisation setup; this project keeps it indoors instead.

### Nav2 parameter changes

Nav2 runs on TurtleBot3's stock parameters with the changes listed here, which live in
`src/lcmr_agent/config/nav2_changes.yaml`. Each was tried on its own and kept only if it clearly helped.

| # | Parameter (controller, DWB `FollowPath`) | Stock | Now | Kept |
| --- | --- | --- | --- | --- |
| 1 | `forward_prune_distance` | 2.0 m | 1.0 m | yes |

#### Change 1: `forward_prune_distance` 2.0 → 1.0

- **Symptom:** on trips that turn round the end of a wall, the robot stopped in open floor about
  0.7 m from the wall and sat there until Nav2 reported "Failed to make progress" and, often, aborted
  the trip. It happened on both sides of the wall between the living room and the study, and outside
  the bathroom door (before the bathroom goal was moved in line with its door). Localisation was not the cause: AMCL was within 0.2 m of the true pose each time.
- **Cause, from the controller's own scores:** during a stall none of its 819 candidate
  trajectories was blocked by an obstacle and nothing was within 0.5 m, yet the best-scoring one was
  to stand still.
  The controller steers towards the point where the path leaves a set radius. With the stock value
  that point was 1.5 m away, straight across the wall, while the path itself ran along the wall to
  its end. The robot turned to face that point; from there any forward motion left the path and
  scored worse than not moving.
- **Change:** `forward_prune_distance` set to 1.0 m, so the point the controller steers towards
  stays on the robot's side of the corner. Nothing else differs from stock.
- **Test:** three laps of dock → bedroom → bathroom → bedroom → dock (13 trips), which crosses every
  place that stalled, once on stock parameters and once with the change. Times are wall-clock with
  the simulator at about half real-time.

| Route | Stock: reached | Stock: time per trip | Changed: reached | Changed: time per trip |
| --- | --- | --- | --- | --- |
| dock → bedroom | 1 of 2 | 317–331 s | 4 of 4 | 89–96 s |
| bedroom → bathroom | 1 of 2 | 386–429 s | 3 of 3 | 223–231 s |
| bathroom → bedroom | 2 of 2 | 247–440 s | 3 of 3 | 227–238 s |
| bedroom → dock | 1 of 3 | 258–410 s | 3 of 3 | 99–102 s |
| other (started where a failed trip ended) | 4 of 4 | 53–132 s | none | |
| **All 13 trips** | **9 of 13** | **3,520 s in total** | **13 of 13** | **2,037 s in total** |

| Over the 13 trips | Stock | Changed |
| --- | --- | --- |
| Trips with a stall of 15 s or more | 9 | 1 |
| Time spent stalled | 1,903 s | 15 s |
| "Failed to make progress" reports from Nav2 | 89 | 0 |

The one 15-second pause with the change is the robot turning round inside the bathroom before it
leaves, not a stall at a corner.

