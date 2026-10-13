"""Release requests, serve passengers, and move elevators one tick at a time."""

from dataclasses import dataclass, field

from .domain import (
    PassengerOutcome,
    PositionRow,
    Request,
    SimulationResult,
    Stop,
    summarize,
    validate_inputs,
)
from .scheduler import DISPATCHERS, STOP_SCHEDULERS, direction


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


def serve(car, passengers, capacity, time):
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
            if len(car.onboard) >= capacity:
                raise ValueError(f"{car.id}: capacity exceeded")
            trip_direction = direction(car.floor, passenger.request.dest)
            if any(
                direction(car.floor, passengers[other].request.dest) != trip_direction
                for other in car.onboard
            ):
                raise ValueError(f"{car.id}: incompatible passenger directions")
            car.onboard.append(pid)
            car.direction = trip_direction
            passenger.boarding_time = time


def move(car, passengers):
    if not car.route:
        return
    next_direction = direction(car.floor, car.route[0].floor)
    if any(
        direction(car.floor, passengers[pid].request.dest) != next_direction
        for pid in car.onboard
    ):
        raise ValueError(f"{car.id}: occupied car cannot reverse")
    car.direction = next_direction
    car.floor += next_direction


def simulate(requests, config, *, dispatcher="nearest-car", stop_scheduler="look"):
    """Immediately assign each arriving request and finish when everyone exits."""
    dispatch = DISPATCHERS.get(dispatcher)
    if dispatch is None:
        raise ValueError(f"unknown dispatcher: {dispatcher}")
    schedule_stops = STOP_SCHEDULERS.get(stop_scheduler)
    if schedule_stops is None:
        raise ValueError(f"unknown stop scheduler: {stop_scheduler}")
    requests = validate_inputs(requests, config)
    cars = [CarState(f"e{index + 1}") for index in range(config.elevator_count)]
    passengers = {}
    positions = []
    index = 0
    time = 0

    def plan_stops(car, request):
        """Preview an assignment on a copy, without assigning anyone for real."""
        preview = dict(passengers)
        preview[request.id] = PassengerState(request, car.id)
        return schedule_stops(car, preview, config.capacity)

    while True:
        # The scheduler receives only requests whose timestamp has arrived.
        while index < len(requests) and requests[index].time == time:
            request = requests[index]
            # Dispatch picks the car. LOOK then orders that car's stops.
            car = dispatch(cars, request, plan_stops)
            passengers[request.id] = PassengerState(request, car.id)
            car.route = schedule_stops(car, passengers, config.capacity)
            index += 1
        for car in cars:
            serve(car, passengers, config.capacity, time)
        positions.append(PositionRow(time, tuple(car.floor for car in cars)))
        if index == len(requests) and all(
            passenger.arrival_time is not None for passenger in passengers.values()
        ):
            break
        for car in cars:
            move(car, passengers)
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
