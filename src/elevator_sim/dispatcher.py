"""Choose which elevator receives each request."""

from .domain import direction


def dispatch_nearest_car(cars, request):
    """Choose the closest current floor; equal distances use elevator order."""
    return min(cars, key=lambda car: abs(car.floor - request.source))


def dispatch_direction_aware(cars, request):
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


def dispatch_lowest_cost(cars, request, routes):
    """Choose the least added total time using each car's previewed route."""
    return min(cars, key=lambda car: added_time_cost(car, request, routes[car.id]))


DISPATCHERS = {
    "nearest-car": dispatch_nearest_car,
    "direction-aware": dispatch_direction_aware,
    "cost": dispatch_lowest_cost,
}
