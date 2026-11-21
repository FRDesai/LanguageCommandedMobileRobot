"""Named locations: the only places the robot can be sent."""
import math
from pathlib import Path

import yaml

from .robot import Pose


def _normalise(name: str) -> str:
    return name.strip().lower()


class Locations:
    def __init__(self, poses: dict[str, Pose]):
        self._poses = poses

    @classmethod
    def load(cls, path) -> "Locations":
        data = yaml.safe_load(Path(path).read_text()) or {}
        entries = data.get("locations") or {}
        if not entries:
            raise ValueError(f"{path}: no locations defined")
        poses = {}
        for name, entry in entries.items():
            try:
                poses[_normalise(str(name))] = Pose(
                    float(entry["x"]), float(entry["y"]), float(entry["yaw"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{path}: location '{name}' needs numeric x, y and yaw") from error
        return cls(poses)

    def names(self) -> list[str]:
        return list(self._poses)

    def get(self, name: str) -> Pose | None:
        return self._poses.get(_normalise(name))

    def nearest(self, x: float, y: float) -> str:
        return min(self._poses, key=lambda n: math.hypot(self._poses[n].x - x, self._poses[n].y - y))
