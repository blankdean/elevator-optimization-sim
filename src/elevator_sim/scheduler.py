"""Dispatch chooses an elevator; stop scheduling orders that elevator's visits."""

from .domain import Stop


def direction(source, dest):
    """Return 1 for up, -1 for down, or 0 for the same floor."""
    return (dest > source) - (dest < source)


def dispatch_nearest_car(cars, request, plan_stops=None):
    """Choose the closest current floor; equal distances use elevator order."""
    return min(cars, key=lambda car: abs(car.floor - request.source))


def dispatch_direction_aware(cars, request, plan_stops=None):
    """Choose the nearest idle car or one approaching in the rider's direction."""
    trip_direction = direction(request.source, request.dest)
    candidates = []
    for car in cars:
        idle = not car.route and not car.onboard
        same_direction = car.direction == trip_direction
        pickup_ahead = direction(car.floor, request.source) in (0, car.direction)
        if idle or (same_direction and pickup_ahead):
            candidates.append(car)
    # If every car is unsuitable, still assign the request to the nearest one.
    return dispatch_nearest_car(candidates or cars, request)


def route_arrival_times(car, route):
    """Predict ticks until each drop-off by adding the distances between stops."""
    floor = car.floor
    elapsed = 0
    arrivals = {}
    for stop in route:
        elapsed += abs(stop.floor - floor)
        for passenger_id in stop.dropoffs:
            arrivals[passenger_id] = elapsed
        floor = stop.floor
    return arrivals


def added_time_cost(car, request, new_route):
    """New rider's total time plus the change in all existing riders' arrival times."""
    before = route_arrival_times(car, car.route)
    after = route_arrival_times(car, new_route)
    existing_delay = sum(after[pid] - before[pid] for pid in before)
    return after[request.id] + existing_delay


def dispatch_lowest_cost(cars, request, plan_stops):
    """Try the new passenger in each car and choose the least added total time."""
    chosen = None
    lowest_cost = None
    for car in cars:
        new_route = plan_stops(car, request)
        cost = added_time_cost(car, request, new_route)
        if lowest_cost is None or cost < lowest_cost:
            chosen = car
            lowest_cost = cost
    return chosen


def target_floors(trips, waiting, onboard, capacity):
    """Visit riders' destinations; consider pickup floors when seats are available."""
    targets = [trips[pid].dest for pid in onboard]
    if len(onboard) < capacity:
        targets += [trips[pid].source for pid in waiting]
    return targets


def schedule_look_stops(car, passengers, capacity):
    """Plan stops for this car's assigned riders, without moving the real car."""
    trips = {}
    waiting = []
    for passenger in passengers.values():
        if passenger.elevator_id != car.id or passenger.arrival_time is not None:
            continue
        trips[passenger.request.id] = passenger.request
        if passenger.boarding_time is None:
            waiting.append(passenger.request.id)

    # Work on copies: boarding and movement here are predictions.
    onboard = list(car.onboard)
    floor, sweep = car.floor, car.direction
    route = []
    if not onboard and not car.route:
        sweep = 0
    while waiting or onboard:
        # 1. An idle car heads toward its oldest waiting passenger.
        if sweep == 0:
            oldest = trips[waiting[0]]
            sweep = direction(floor, oldest.source) or direction(
                oldest.source, oldest.dest
            )

        # 2. Drop off riders at this floor, freeing their seats.
        dropoffs = [pid for pid in onboard if trips[pid].dest == floor]
        for pid in dropoffs:
            onboard.remove(pid)
        targets = target_floors(trips, waiting, onboard, capacity)

        # 3. An empty car can turn if it has no work ahead in this direction.
        if not onboard and not any(
            direction(floor, target) == sweep for target in targets
        ):
            compatible_here = any(
                trips[pid].source == floor
                and direction(floor, trips[pid].dest) == sweep
                for pid in waiting
            )
            if not compatible_here:
                sweep = -sweep

        # 4. Pick up riders here who want this direction, while seats remain.
        pickups = []
        for pid in waiting[:]:
            trip = trips[pid]
            if (
                trip.source == floor
                and direction(floor, trip.dest) == sweep
                and len(onboard) < capacity
            ):
                pickups.append(pid)
                onboard.append(pid)
                waiting.remove(pid)
        if dropoffs or pickups:
            route.append(Stop(floor, tuple(pickups), tuple(dropoffs)))

        # 5. Head to the nearest useful floor in the current direction.
        targets = target_floors(trips, waiting, onboard, capacity)
        ahead = [target for target in targets if direction(floor, target) == sweep]
        if ahead:
            floor = min(ahead, key=lambda target: abs(target - floor))
        elif waiting or onboard:
            if onboard:
                raise ValueError("LOOK encountered an occupied reversal")
            sweep = -sweep
    return route


# Add another function and a name here when you want to try another method.
DISPATCHERS = {
    "nearest-car": dispatch_nearest_car,
    "direction-aware": dispatch_direction_aware,
    "cost": dispatch_lowest_cost,
}
STOP_SCHEDULERS = {"look": schedule_look_stops}
