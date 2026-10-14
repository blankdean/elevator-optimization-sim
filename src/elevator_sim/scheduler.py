"""Plan the order of an elevator's pickups and drop-offs."""

from .domain import Stop, direction


def target_floors(trips, waiting, onboard, capacity):
    """Visit riders' destinations; consider pickup floors when seats are available."""
    targets = [trips[pid].dest for pid in onboard]
    if len(onboard) < capacity:
        targets += [trips[pid].source for pid in waiting]
    return targets


def assigned_trips(car, passengers):
    """Collect this car's active requests in arrival order."""
    trips = {}
    waiting = []
    for passenger in passengers.values():
        if passenger.elevator_id != car.id or passenger.arrival_time is not None:
            continue
        trips[passenger.request.id] = passenger.request
        if passenger.boarding_time is None:
            waiting.append(passenger.request.id)
    return trips, waiting


def schedule_look_stops(car, passengers, capacity):
    """Plan stops for this car's assigned riders, without moving the real car."""
    trips, waiting = assigned_trips(car, passengers)
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
            sweep = -sweep
    return route


def schedule_fifo_stops(car, passengers, capacity):
    """Serve the oldest waiting request next, sharing pickups along its trip."""
    trips, waiting = assigned_trips(car, passengers)
    onboard = list(car.onboard)
    floor = car.floor
    route = []

    while waiting or onboard:
        # 1. Drop off riders here before planning any pickups.
        dropoffs = [pid for pid in onboard if trips[pid].dest == floor]
        for pid in dropoffs:
            onboard.remove(pid)
        if dropoffs:
            route.append(Stop(floor, dropoffs=tuple(dropoffs)))

        # 2. When empty, go straight to the oldest waiting rider.
        if not onboard:
            if not waiting:
                break
            oldest = trips[waiting[0]]
            floor = oldest.source
            sweep = direction(floor, oldest.dest)
        else:
            sweep = direction(floor, trips[onboard[0]].dest)

        # 3. Share this trip with compatible riders here, while seats remain.
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
        if pickups:
            route.append(Stop(floor, pickups=tuple(pickups)))

        # 4. Visit drop-offs and compatible pickups before the last destination.
        targets = [trips[pid].dest for pid in onboard]
        last_floor = max(targets, key=lambda target: abs(target - floor))
        if len(onboard) < capacity:
            for pid in waiting:
                trip = trips[pid]
                if (
                    direction(floor, trip.source) == sweep
                    and direction(trip.source, trip.dest) == sweep
                    and abs(trip.source - floor) <= abs(last_floor - floor)
                ):
                    targets.append(trip.source)
        floor = min(targets, key=lambda target: abs(target - floor))
    return route


STOP_SCHEDULERS = {"look": schedule_look_stops, "fifo": schedule_fifo_stops}
