"""Replays the fixed test set and prints the metrics table."""
import argparse
import time
from pathlib import Path

from .console import Console
from .evaluation import Case, format_report, load_cases, load_events, score
from .event_log import EventLog


def replay(cases: dict[str, Case], console: Console, robot, log: EventLog, runs: int) -> None:
    for run in range(1, runs + 1):
        for case in cases.values():
            # Every case starts on a full battery unless it sets its own level, so
            # the trips of earlier cases cannot trip the low-battery rule in later ones.
            robot.set_battery_percent(100.0 if case.battery_percent is None else case.battery_percent)
            log.write("case_started", case_id=case.id, run=run, command=case.command)

            console.submit(case.command)
            if case.stop_after_s is not None:
                time.sleep(case.stop_after_s)
                console.submit("stop")
            console.wait()

            log.write("case_finished", case_id=case.id, run=run)
            if case.battery_percent is not None:
                robot.set_battery_percent(100.0)


def main() -> None:
    from .app import add_common_arguments, build

    parser = argparse.ArgumentParser(description="Replay the test set and score it.")
    add_common_arguments(parser)
    parser.add_argument("--cases", required=True, help="test-set YAML file")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--score-only", action="store_true", help="score an existing log without replaying")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not args.score_only:
        if Path(args.log).exists():
            parser.error(f"{args.log} already exists; choose a new --log so runs are not mixed")
        session, robot, _, log = build(args)
        try:
            replay(cases, Console(session, write=lambda reply: print(f"  -> {reply}")), robot, log, args.runs)
        finally:
            robot.shutdown()
    print(format_report(score(load_events(args.log), cases)))


if __name__ == "__main__":
    main()
