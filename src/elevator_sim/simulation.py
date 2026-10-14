"""Release requests, serve passengers, and move elevators one tick at a time."""

from dataclasses import dataclass, field

from .dispatcher import DISPATCHERS
from .domain import (
    PassengerOutcome,
    PositionRow,
    Request,
    SimulationResult,
    Stop,
    direction,
    summarize,
    validate_inputs,
)
from .scheduler import STOP_SCHEDULERS


@dataclass
class CarState:
    id: str
    floor: int = 1
    direction: int = 0
    onboard: list[str] = field(default_factory=list)
    route: list[Stop] = field(default_factory=list)


@dataclass
class PassengerState:
    request: Request
    elevator_id: str
    boarding_time: int | None = None
    arrival_time: int | None = None


def assign_request(request, cars, passengers, capacity, dispatcher, stop_scheduler):
    """Choose a car, assign the rider, and update that car's stops."""
    dispatch = DISPATCHERS[dispatcher]
    schedule_stops = STOP_SCHEDULERS[stop_scheduler]
    if dispatcher == "cost":
        routes = {}
        for car in cars:
            preview = dict(passengers)
            preview[request.id] = PassengerState(request, car.id)
            routes[car.id] = schedule_stops(car, preview, capacity)
        car = dispatch(cars, request, routes)
    else:
        car = dispatch(cars, request)
    passengers[request.id] = PassengerState(request, car.id)
    car.route = schedule_stops(car, passengers, capacity)


def serve(car, passengers, time):
    stops = []
    while car.route and car.route[0].floor == car.floor:
        stops.append(car.route.pop(0))
    # All drop-offs happen first, freeing seats for pickups at this floor.
    for stop in stops:
        for pid in stop.dropoffs:
            car.onboard.remove(pid)
            passengers[pid].arrival_time = time
    for stop in stops:
        for pid in stop.pickups:
            passenger = passengers[pid]
            car.onboard.append(pid)
            car.direction = direction(car.floor, passenger.request.dest)
            passenger.boarding_time = time


def move(car):
    if not car.route:
        return
    car.direction = direction(car.floor, car.route[0].floor)
    car.floor += car.direction


def simulate(requests, config, *, dispatcher="nearest-car", stop_scheduler="look"):
    """Immediately assign each arriving request and finish when everyone exits."""
    if dispatcher not in DISPATCHERS:
        raise ValueError(f"unknown dispatcher: {dispatcher}")
    if stop_scheduler not in STOP_SCHEDULERS:
        raise ValueError(f"unknown stop scheduler: {stop_scheduler}")
    requests = validate_inputs(requests, config)
    cars = [CarState(f"e{index + 1}") for index in range(config.elevator_count)]
    passengers = {}
    positions = []
    index = 0
    time = 0

    while True:
        # 1. Release and assign requests arriving on this tick.
        while index < len(requests) and requests[index].time == time:
            assign_request(
                requests[index],
                cars,
                passengers,
                config.capacity,
                dispatcher,
                stop_scheduler,
            )
            index += 1

        # 2. Drop off and board passengers at each car's current floor.
        for car in cars:
            serve(car, passengers, time)

        # 3. Record positions, including the final tick.
        positions.append(PositionRow(time, tuple(car.floor for car in cars)))
        finished = index == len(requests) and all(
            passenger.arrival_time is not None for passenger in passengers.values()
        )
        if finished:
            break

        # 4. Move each car one floor, then advance time.
        for car in cars:
            move(car)
        time += 1
    outcomes = tuple(
        PassengerOutcome(
            id=request.id,
            source=request.source,
            dest=request.dest,
            elevator_id=passengers[request.id].elevator_id,
            request_time=request.time,
            boarding_time=passengers[request.id].boarding_time,
            arrival_time=passengers[request.id].arrival_time,
        )
        for request in requests
    )
    return SimulationResult(
        config,
        tuple(positions),
        outcomes,
        time,
        summarize(outcomes, time),
        dispatcher=dispatcher,
        stop_scheduler=stop_scheduler,
    )
