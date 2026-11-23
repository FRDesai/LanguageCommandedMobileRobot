"""Terminal chat with the robot.

Commands run on a worker thread so the prompt stays live: typing "stop" while
the robot is driving cancels the trip at once.
"""
import argparse
import threading

from .session import Session


class Console:
    def __init__(self, session: Session, write=print):
        self._session = session
        self._write = write
        self._worker: threading.Thread | None = None

    def submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._session.is_stop(text):
            self._write(self._session.handle(text))
        elif self._worker is not None and self._worker.is_alive():
            self._write('Still working on the last command. Type "stop" to cancel it.')
        else:
            self._worker = threading.Thread(
                target=lambda: self._write(self._session.handle(text)), daemon=True)
            self._worker.start()

    def wait(self) -> None:
        """Block until the running command, if any, has finished."""
        if self._worker is not None:
            self._worker.join()


def main() -> None:
    from .app import add_common_arguments, build

    parser = argparse.ArgumentParser(description="Send plain-English commands to the robot.")
    add_common_arguments(parser)
    args, _ = parser.parse_known_args()  # leave the --ros-args that ros2 launch appends
    session, robot, locations, _ = build(args)
    console = Console(session, write=lambda reply: print(f"\nrobot> {reply}\n> ", end="", flush=True))

    print(f'Rooms: {", ".join(locations.names())}. Type a command, "stop" to cancel, "quit" to exit.')
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in {"quit", "exit"}:
            break
        console.submit(line)
    robot.cancel_navigation()
    console.wait()
    robot.shutdown()
    print()


if __name__ == "__main__":
    main()
