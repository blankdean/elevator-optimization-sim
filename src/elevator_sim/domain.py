"""Requests, building configuration, and simulation results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    time: int
    id: str
    source: int
    dest: int


@dataclass(frozen=True)
class SimulationConfig:
    floors: int
    elevator_count: int
    capacity: int


@dataclass(frozen=True)
class Stop:
    floor: int
    pickups: tuple[str, ...] = ()
    dropoffs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PositionRow:
    time: int
    floors: tuple[int, ...]


@dataclass(frozen=True)
class PassengerOutcome:
    id: str
    source: int
    dest: int
    elevator_id: str
    request_time: int
    boarding_time: int
    arrival_time: int

    @property
    def wait_time(self):
        return self.boarding_time - self.request_time

    @property
    def travel_time(self):
        return self.arrival_time - self.boarding_time

    @property
    def total_time(self):
        return self.arrival_time - self.request_time


@dataclass(frozen=True)
class Summary:
    completed_passengers: int
    min_wait: int | None
    max_wait: int | None
    mean_wait: float | None
    min_total: int | None
    max_total: int | None
    mean_total: float | None
    completion_time: int


def summarize(passengers, completion_time):
    waits = [passenger.wait_time for passenger in passengers]
    totals = [passenger.total_time for passenger in passengers]
    count = len(passengers)
    return Summary(
        completed_passengers=count,
        min_wait=min(waits) if count else None,
        max_wait=max(waits) if count else None,
        mean_wait=sum(waits) / count if count else None,
        min_total=min(totals) if count else None,
        max_total=max(totals) if count else None,
        mean_total=sum(totals) / count if count else None,
        completion_time=completion_time,
    )


@dataclass(frozen=True)
class SimulationResult:
    config: SimulationConfig
    positions: tuple[PositionRow, ...]
    passengers: tuple[PassengerOutcome, ...]
    completion_time: int
    summary: Summary
    dispatcher: str = "nearest-car"
    stop_scheduler: str = "look"


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def validate_inputs(requests, config):
    integer(config.floors, "floors", 2)
    integer(config.elevator_count, "elevator_count", 1)
    integer(config.capacity, "capacity", 1)
    requests = tuple(requests)
    ids = set()
    for request in requests:
        integer(request.time, "request time")
        if not isinstance(request.id, str) or not request.id or request.id in ids:
            raise ValueError("passenger IDs must be nonempty and unique")
        ids.add(request.id)
        for floor in (request.source, request.dest):
            integer(floor, "request floor", 1)
            if floor > config.floors:
                raise ValueError("request floor outside building")
        if request.source == request.dest:
            raise ValueError("request endpoints must differ")
    # Equal-time requests keep their input order.
    return tuple(sorted(requests, key=lambda request: request.time))
