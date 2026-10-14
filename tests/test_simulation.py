import csv
import json

import pytest

from elevator_sim import Request, SimulationConfig, simulate
from elevator_sim.cli import choose_option, interactive_args, main
from elevator_sim.dispatcher import (
    added_time_cost,
    dispatch_direction_aware,
    dispatch_nearest_car,
)
from elevator_sim.domain import Stop
from elevator_sim.simulation import CarState


def test_single_passenger_timing_and_positions():
    result = simulate([Request(0, "a", 1, 4)], SimulationConfig(5, 1, 1))
    passenger = result.passengers[0]
    assert (passenger.boarding_time, passenger.arrival_time) == (0, 3)
    assert (passenger.wait_time, passenger.travel_time, passenger.total_time) == (
        0,
        3,
        3,
    )
    assert [(row.time, row.floors) for row in result.positions] == [
        (0, (1,)),
        (1, (2,)),
        (2, (3,)),
        (3, (4,)),
    ]
    assert result.completion_time == 3


@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_compatible_passengers_share_the_trip(stop_scheduler):
    result = simulate(
        [Request(0, "a", 1, 8), Request(0, "b", 3, 6)],
        SimulationConfig(10, 1, 2),
        stop_scheduler=stop_scheduler,
    )
    first, second = result.passengers
    assert first.arrival_time == 7
    assert (second.boarding_time, second.arrival_time) == (2, 5)


@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_full_car_returns_for_the_waiting_passenger(stop_scheduler):
    result = simulate(
        [Request(0, "a", 1, 8), Request(0, "b", 3, 6)],
        SimulationConfig(10, 1, 1),
        stop_scheduler=stop_scheduler,
    )
    first, second = result.passengers
    assert first.arrival_time == 7
    assert (second.boarding_time, second.arrival_time) == (12, 15)


@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_opposing_trip_waits_until_the_car_can_turn(stop_scheduler):
    result = simulate(
        [Request(0, "a", 1, 4), Request(0, "b", 6, 2)],
        SimulationConfig(10, 1, 2),
        stop_scheduler=stop_scheduler,
    )
    first, second = result.passengers
    assert first.arrival_time == 3
    assert (second.boarding_time, second.arrival_time) == (5, 9)
    assert max(row.floors[0] for row in result.positions) == 6


def test_nearest_car_dispatch_uses_current_distance_and_stable_ties():
    result = simulate(
        [Request(0, "a", 1, 8), Request(1, "b", 1, 3), Request(2, "c", 3, 5)],
        SimulationConfig(10, 2, 1),
    )
    assert [passenger.elevator_id for passenger in result.passengers] == [
        "e1",
        "e2",
        "e1",
    ]
    # e1 is closest to c, even though it is full and must return later.
    assert result.passengers[2].boarding_time == 12


def test_direction_dispatch_prefers_an_approaching_car():
    request = Request(0, "new", 4, 8)
    wrong_way = CarState("wrong-way", floor=3, direction=-1, route=[Stop(1)])
    passed_pickup = CarState("passed", floor=5, direction=1, route=[Stop(10)])
    approaching = CarState("approaching", floor=2, direction=1, route=[Stop(10)])
    cars = [wrong_way, passed_pickup, approaching]
    assert dispatch_nearest_car(cars, request) is wrong_way
    assert dispatch_direction_aware(cars, request) is approaching


def test_direction_dispatch_for_a_downward_trip():
    request = Request(0, "new", 6, 2)
    wrong_way = CarState("wrong-way", floor=7, direction=1, route=[Stop(10)])
    approaching = CarState("approaching", floor=8, direction=-1, route=[Stop(1)])
    assert dispatch_direction_aware([wrong_way, approaching], request) is approaching


def test_direction_dispatch_considers_idle_cars_and_has_a_nearest_fallback():
    request = Request(0, "new", 4, 8)
    wrong_way = CarState("wrong-way", floor=3, direction=-1, route=[Stop(1)])
    approaching = CarState("approaching", floor=1, direction=1, route=[Stop(10)])
    # An idle car can retain its previous direction after its last trip.
    idle = CarState("idle", floor=6, direction=-1)
    assert dispatch_direction_aware([wrong_way, approaching, idle], request) is idle
    passed_pickup = CarState("passed", floor=5, direction=1, route=[Stop(10)])
    assert dispatch_direction_aware([wrong_way, passed_pickup], request) is wrong_way


def test_cost_counts_the_new_trip_and_delay_to_every_existing_rider():
    car = CarState(
        "e1",
        route=[
            Stop(3, pickups=("a",)),
            Stop(2, pickups=("c",)),
            Stop(1, dropoffs=("a", "c")),
        ],
    )
    request = Request(0, "b", 1, 4)
    new_route = [
        Stop(1, pickups=("b",)),
        Stop(4, dropoffs=("b",)),
        Stop(3, pickups=("a",)),
        Stop(2, pickups=("c",)),
        Stop(1, dropoffs=("a", "c")),
    ]
    # b takes 3 ticks; a and c each arrive 2 ticks later: 3 + 2 + 2 = 7.
    assert added_time_cost(car, request, new_route) == 7


@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_cost_dispatch_avoids_waiting_for_a_nearby_full_car(stop_scheduler):
    result = simulate(
        [Request(0, "a", 1, 8), Request(1, "b", 1, 3), Request(2, "c", 3, 5)],
        SimulationConfig(10, 2, 1),
        dispatcher="cost",
        stop_scheduler=stop_scheduler,
    )
    # e1 is closer, but e2 can unload b and pick up c on tick 3.
    assert result.passengers[2].elevator_id == "e2"
    assert result.passengers[2].boarding_time == 3
    assert result.passengers[2].arrival_time == 5


@pytest.mark.parametrize("dispatcher", ["nearest-car", "direction-aware", "cost"])
@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_ticks_include_gaps_and_future_requests_do_not_change_the_past(
    dispatcher, stop_scheduler
):
    config = SimulationConfig(10, 2, 2)
    past = [Request(0, "a", 1, 4), Request(1, "b", 3, 6)]
    before = simulate(
        past, config, dispatcher=dispatcher, stop_scheduler=stop_scheduler
    )
    future = Request(10, "future", 8, 1)
    # Unsorted input is accepted, but scheduling still waits for each timestamp.
    after = simulate(
        [future, *past], config, dispatcher=dispatcher, stop_scheduler=stop_scheduler
    )
    assert after.positions[: len(before.positions)] == before.positions
    assert after.passengers[: len(past)] == before.passengers
    assert [row.time for row in after.positions] == list(
        range(after.completion_time + 1)
    )


@pytest.mark.parametrize("dispatcher", ["nearest-car", "direction-aware", "cost"])
@pytest.mark.parametrize("stop_scheduler", ["look", "fifo"])
def test_mixed_workload_completes_with_capacity_and_direction_constraints(
    dispatcher, stop_scheduler
):
    requests = [
        Request(0, "a", 1, 9),
        Request(0, "b", 1, 5),
        Request(1, "c", 3, 8),
        Request(2, "d", 9, 1),
        Request(2, "e", 5, 2),
        Request(3, "f", 2, 7),
        Request(4, "g", 8, 3),
        Request(8, "h", 1, 6),
        Request(10, "i", 6, 1),
    ]
    config = SimulationConfig(9, 2, 2)
    result = simulate(
        requests, config, dispatcher=dispatcher, stop_scheduler=stop_scheduler
    )
    assert result == simulate(
        requests, config, dispatcher=dispatcher, stop_scheduler=stop_scheduler
    )
    assert {passenger.id for passenger in result.passengers} == {
        request.id for request in requests
    }
    assert len(result.passengers) == len(requests)
    assert all(
        passenger.request_time <= passenger.boarding_time < passenger.arrival_time
        for passenger in result.passengers
    )
    for row in result.positions:
        for index, floor in enumerate(row.floors):
            assert 1 <= floor <= config.floors
            onboard = [
                passenger
                for passenger in result.passengers
                if passenger.elevator_id == f"e{index + 1}"
                and passenger.boarding_time <= row.time < passenger.arrival_time
            ]
            assert len(onboard) <= config.capacity
            if row.time < result.completion_time:
                step = result.positions[row.time + 1].floors[index] - floor
                assert abs(step) <= 1
                assert all((passenger.dest - floor) * step > 0 for passenger in onboard)


def test_basic_invalid_inputs_are_rejected():
    config = SimulationConfig(5, 1, 1)
    with pytest.raises(ValueError, match="unique"):
        simulate([Request(0, "a", 1, 4), Request(1, "a", 2, 3)], config)
    with pytest.raises(ValueError, match="outside building"):
        simulate([Request(0, "a", 1, 6)], config)
    with pytest.raises(ValueError, match="capacity"):
        simulate([], SimulationConfig(5, 1, 0))
    with pytest.raises(ValueError, match="unknown dispatcher"):
        simulate([], config, dispatcher="missing")
    with pytest.raises(ValueError, match="unknown stop scheduler"):
        simulate([], config, stop_scheduler="missing")


@pytest.mark.parametrize(
    "dispatcher,stop_scheduler", [("nearest-car", "look"), ("cost", "fifo")]
)
def test_cli_writes_complete_positions_and_known_summary(
    tmp_path, capsys, dispatcher, stop_scheduler
):
    requests = tmp_path / "requests.csv"
    requests.write_text("time,id,source,dest\n0,a,1,4\n0,b,1,2\n")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"floors": 5, "elevator_count": 1, "capacity": 1}))
    output = tmp_path / "reports"
    assert (
        main(
            [
                "--requests",
                str(requests),
                "--config",
                str(config),
                "--output",
                str(output),
                "--dispatcher",
                dispatcher,
                "--stop-scheduler",
                stop_scheduler,
            ]
        )
        == 0
    )
    with (output / "positions.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert list(rows[0]) == ["time", "e1"]
    assert [int(row["time"]) for row in rows] == list(range(8))
    assert [int(row["e1"]) for row in rows] == [1, 2, 3, 4, 3, 2, 1, 2]
    summary = json.loads((output / "summary.json").read_text())
    assert summary == {
        "dispatcher": dispatcher,
        "stop_scheduler": stop_scheduler,
        "configuration": {"floors": 5, "elevator_count": 1, "capacity": 1},
        "completed_passengers": 2,
        "min_wait": 0,
        "max_wait": 6,
        "mean_wait": 3,
        "min_total": 3,
        "max_total": 7,
        "mean_total": 5,
        "completion_time": 7,
    }
    assert {path.name for path in output.iterdir()} == {"positions.csv", "summary.json"}
    assert "2 passengers" in capsys.readouterr().out


def test_numbered_menu_accepts_a_valid_number_after_an_invalid_one(monkeypatch):
    answers = iter(["9", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert choose_option("Dispatcher", ["nearest-car", "cost"]) == "cost"


def test_default_reports_keep_dispatchers_schedulers_and_buildings_separate(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    requests = tmp_path / "commute.csv"
    requests.write_text("time,id,source,dest\n0,a,1,4\n")
    basic = tmp_path / "basic.json"
    basic.write_text(json.dumps({"floors": 5, "elevator_count": 1, "capacity": 1}))
    larger = tmp_path / "larger.json"
    larger.write_text(json.dumps({"floors": 8, "elevator_count": 2, "capacity": 2}))

    cases = [
        (basic, "nearest-car", "look"),
        (basic, "cost", "look"),
        (basic, "cost", "fifo"),
        (larger, "cost", "fifo"),
    ]
    for config, dispatcher, scheduler in cases:
        assert (
            main(
                [
                    "--requests",
                    str(requests),
                    "--config",
                    str(config),
                    "--dispatcher",
                    dispatcher,
                    "--stop-scheduler",
                    scheduler,
                ]
            )
            == 0
        )

    for config, dispatcher, scheduler in cases:
        directory = tmp_path / "out" / f"commute-{config.stem}" / scheduler / dispatcher
        summary = json.loads((directory / "summary.json").read_text())
        assert summary["dispatcher"] == dispatcher
        assert summary["stop_scheduler"] == scheduler
        assert summary["configuration"] == json.loads(config.read_text())
        assert (directory / "positions.csv").is_file()


def test_fifo_starts_the_oldest_waiting_trip_after_unloading():
    result = simulate(
        [Request(0, "a", 1, 4), Request(0, "b", 6, 2), Request(0, "c", 4, 8)],
        SimulationConfig(10, 1, 2),
        stop_scheduler="fifo",
    )
    first, oldest, younger = result.passengers
    assert first.arrival_time == 3
    # b is older than c, so the empty car goes to b instead of boarding c here.
    assert (oldest.boarding_time, oldest.arrival_time) == (5, 9)
    assert (younger.boarding_time, younger.arrival_time) == (11, 15)


def test_interactive_menu_selects_example_dispatcher_and_scheduler(monkeypatch):
    answers = iter(["2", "3", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert interactive_args() == [
        "mixed",
        "--dispatcher",
        "cost",
        "--stop-scheduler",
        "fifo",
    ]
