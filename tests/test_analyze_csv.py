import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import analyze_csv


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_flags_high_temperature_deviation(tmp_path):
    path = tmp_path / "data.csv"
    write_csv(
        path,
        [{"time": "Mon 2 PM", "temp": 17, "target_temp": 22, "runtime": 10, "occupancy": 1}],
        ["time", "temp", "target_temp", "runtime", "occupancy"],
    )

    issues, score, total_cost, occupancy_wasted = analyze_csv(path)

    assert len(issues) == 1
    assert issues[0]["issue"] == "Temperature deviation"
    assert issues[0]["severity"] == "High"
    assert total_cost == 60


def test_flags_unoccupied_runtime(tmp_path):
    path = tmp_path / "data.csv"
    write_csv(
        path,
        [{"time": "Tue 10 AM", "temp": 24, "target_temp": 24, "runtime": 30, "occupancy": 0}],
        ["time", "temp", "target_temp", "runtime", "occupancy"],
    )

    issues, score, total_cost, occupancy_wasted = analyze_csv(path)

    assert len(issues) == 1
    assert issues[0]["issue"] == "Unnecessary runtime"
    assert occupancy_wasted == 30


def test_no_issues_gives_perfect_score(tmp_path):
    path = tmp_path / "data.csv"
    write_csv(
        path,
        [{"time": "Wed 3 PM", "temp": 22, "target_temp": 22, "runtime": 15, "occupancy": 1}],
        ["time", "temp", "target_temp", "runtime", "occupancy"],
    )

    issues, score, total_cost, occupancy_wasted = analyze_csv(path)

    assert issues == []
    assert total_cost == 0


def test_missing_required_columns_raises(tmp_path):
    path = tmp_path / "data.csv"
    write_csv(path, [{"time": "Mon 2 PM", "notes": "n/a"}], ["time", "notes"])

    with pytest.raises(ValueError):
        analyze_csv(path)
