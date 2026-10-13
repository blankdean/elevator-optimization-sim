"""Write the required position log and passenger summary statistics."""

import csv
import json
from dataclasses import asdict
from pathlib import Path


def write_result(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "positions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["time", *(f"e{i + 1}" for i in range(result.config.elevator_count))]
        )
        writer.writerows((row.time, *row.floors) for row in result.positions)
    with (directory / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(
            dict(
                dispatcher=result.dispatcher,
                stop_scheduler=result.stop_scheduler,
                configuration=asdict(result.config),
                **asdict(result.summary),
            ),
            stream,
            indent=2,
        )
        stream.write("\n")


def format_value(value):
    return "N/A" if value is None else f"{value:.2f}"


def terminal_summary(result):
    summary = result.summary
    return (
        f"{summary.completed_passengers} passengers; completion {summary.completion_time} ticks\n"
        f"Wait ticks: min {format_value(summary.min_wait)}, "
        f"mean {format_value(summary.mean_wait)}, max {format_value(summary.max_wait)}\n"
        f"Total ticks: min {format_value(summary.min_total)}, "
        f"mean {format_value(summary.mean_total)}, max {format_value(summary.max_total)}"
    )
