"""Read CSV requests and JSON configuration, then run the simulation."""

import argparse
import csv
import json
import sys
from pathlib import Path

from .dispatcher import DISPATCHERS
from .domain import Request, SimulationConfig
from .reporting import terminal_summary, write_result
from .scheduler import STOP_SCHEDULERS
from .simulation import simulate

EXAMPLES = ("tiny", "mixed", "stress")


def choose_option(title, options):
    """Show numbered choices; Enter selects the first option."""
    options = list(options)
    print(f"\n{title}")
    for number, option in enumerate(options, 1):
        print(f"  {number}. {option}")
    while True:
        answer = input("Choose a number [1]: ").strip() or "1"
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print(f"Enter a number from 1 to {len(options)}.")


def interactive_args():
    example = choose_option("Example", EXAMPLES)
    dispatcher = choose_option("Dispatcher", DISPATCHERS)
    stop_scheduler = choose_option("Stop scheduler", STOP_SCHEDULERS)
    return [example, "--dispatcher", dispatcher, "--stop-scheduler", stop_scheduler]


def load_requests(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["time", "id", "source", "dest"]:
            raise ValueError("request CSV header must be time,id,source,dest")
        requests = []
        for number, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("wrong number of fields")
                requests.append(
                    Request(
                        int(row["time"]),
                        row["id"],
                        int(row["source"]),
                        int(row["dest"]),
                    )
                )
            except (ValueError, TypeError) as error:
                raise ValueError(
                    f"invalid request CSV row {number}: {error}"
                ) from error
    return requests


def load_config(path):
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise TypeError("configuration must be a JSON object")
    return SimulationConfig(**data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Elevator simulation with LOOK or FIFO stops; times are ticks."
    )
    parser.add_argument(
        "example",
        nargs="?",
        default="tiny",
        choices=EXAMPLES,
        help="Example workload (default: tiny)",
    )
    parser.add_argument("--requests", help="Custom CSV with time,id,source,dest")
    parser.add_argument(
        "--config",
        help="Building JSON (default: basic.json, or stress.json for stress)",
    )
    parser.add_argument(
        "--output",
        help="Report directory (default: out/<scenario>/<scheduler>/<dispatcher>)",
    )
    parser.add_argument(
        "--dispatcher",
        choices=DISPATCHERS,
        default="nearest-car",
        help="Which elevator receives each request (default: nearest-car)",
    )
    parser.add_argument(
        "--stop-scheduler",
        choices=STOP_SCHEDULERS,
        default="look",
        help="How each elevator orders its stops (default: look)",
    )
    args = parser.parse_args(argv)
    try:
        requests_path = args.requests or f"examples/requests/{args.example}.csv"
        config_name = "stress" if args.example == "stress" else "basic"
        config_path = args.config or f"examples/configs/{config_name}.json"
        workload, building = Path(requests_path).stem, Path(config_path).stem
        scenario = workload if workload == building else f"{workload}-{building}"
        output_path = (
            args.output
            or Path("out") / scenario / args.stop_scheduler / args.dispatcher
        )
        result = simulate(
            load_requests(requests_path),
            load_config(config_path),
            dispatcher=args.dispatcher,
            stop_scheduler=args.stop_scheduler,
        )
        write_result(result, output_path)
        print(terminal_summary(result))
        print(f"Reports saved to {output_path}")
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
