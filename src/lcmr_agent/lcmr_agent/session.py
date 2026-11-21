"""Entry point for every user message: stop filter first, then the agent."""
import time
import uuid

from .agent import Agent
from .event_log import EventLog
from .robot import Robot
from .safety import is_stop_command, looks_like_override


class Session:
    def __init__(self, agent: Agent, robot: Robot, log: EventLog):
        self._agent = agent
        self._robot = robot
        self._log = log

    def is_stop(self, text: str) -> bool:
        return is_stop_command(text)

    def handle(self, text: str) -> str:
        """Process one message. Stop messages are safe to call from any thread."""
        if is_stop_command(text):
            return self._stop(text)

        command_id = uuid.uuid4().hex[:8]
        started = time.time()
        self._log.write("command_received", command_id=command_id, text=text,
                        override_attempt=looks_like_override(text))
        reply = self._agent.run(text, command_id=command_id)
        self._log.write("command_finished", command_id=command_id, reply=reply,
                        duration_s=time.time() - started)
        return reply

    def _stop(self, text: str) -> str:
        started = time.time()
        cancelled = self._robot.cancel_navigation()
        self._log.write("stop", text=text, cancelled=cancelled, duration_s=time.time() - started)
        return "Stopped. Navigation cancelled." if cancelled else "No navigation was in progress."
