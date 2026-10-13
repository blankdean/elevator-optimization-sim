# Elevator simulation

A discrete-time Python simulation with LOOK stop scheduling and three dispatchers.

## Run

Requires **Python 3.11+**. No dependencies or installation needed. From the repo directory:

```sh
python3 run.py
```

Choose an example and dispatcher from the numbered menus. On Windows, use `py run.py`.
To skip the menus:

```sh
python3 run.py mixed --dispatcher nearest-car
python3 run.py mixed --dispatcher direction-aware
python3 run.py stress --dispatcher cost
```

Stress runs 1,000 requests across 60 floors and 12 elevators, each with 8 seats.
Edit `examples/configs/basic.json` for smaller examples or `stress.json` for stress.
Use `python3 run.py --help` for custom input and output options.

## How it works

- **Nearest-car:** assign the elevator closest to the pickup floor.
- **Direction-aware:** prefer idle cars or cars approaching in the rider's direction;
  otherwise use nearest-car.
- **Cost:** preview each elevator's LOOK route and minimize the new rider's total
  time plus the change in arrival times for its existing riders.
- **LOOK:** serve pickups and destinations along a directional sweep, respecting
  capacity. Turn around only when empty.

## Assumptions

- Floors and request times are integers; one tick represents one floor of travel.
- Identical elevators start at floor 1, serve every floor, and stay put when idle.
- Boarding and exiting are instantaneous; riders exit before others board.
- Requests provide both floors and keep their assigned elevator; there are no transfers.
- Capacity is enforced. Riders share a travel direction; occupied cars never reverse.
- Dispatchers use only arrived requests. The input is finite and every rider is served.
- Dispatchers are heuristics, with no guarantee of a globally optimal schedule.

## Output

Results go to `out/<example>/`: `positions.csv` records every elevator each tick;
`summary.json` records minimum, maximum, and average wait and total times.
Wait is request-to-boarding time; total is request-to-arrival time.

## Tests

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

## Time and improvements

This implementation took me about 4 hours. With more time, I would improve fairness
for older requests and measure larger workloads.
