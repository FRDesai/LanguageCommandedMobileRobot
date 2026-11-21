"""Append-only JSON-lines log of commands, tool calls, results and timings."""
import json
import threading
import time
from pathlib import Path


class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, event: str, **fields) -> None:
        line = json.dumps({"ts": time.time(), "event": event, **fields})
        with self._lock, self.path.open("a") as file:
            file.write(line + "\n")
