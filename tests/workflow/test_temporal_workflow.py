"""End-to-end synthetic GIM test for Framework A workflow."""

from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.workflow.temporal_workflow import run_temporal_workflow


def write_gim_day(
    dataset_prefix,
    day,
    *,
    raw_latitude_index,
    longitude_index,
    injections,
):
    year = day.year
    doy = day.timetuple().tm_yday

    year_dir = dataset_prefix.parent / (
        dataset_prefix.name + str(year)
    )
    year_dir.mkdir(parents=True, exist_ok=True)

    # Stored GIM values are 10 times TECu.
    grid = np.full((24, 71, 73), 100.0, dtype=float)

    for timestamp, value in injections.items():
        if timestamp.date() == day.date():
            grid[
                timestamp.hour,
                raw_latitude_index,
                longitude_index,
            ] = value * 10.0

    gim = grid.reshape(24 * 71, 73)

    gim_time = np.array(
        [
            [
                (day + timedelta(hours=h)).year,
                (day + timedelta(hours=h)).month,
                (day + timedelta(hours=h)).day,
                (day + timedelta(hours=h)).hour,
                0,
                0,
            ]
            for h in range(24)
        ],
        dtype=int,
    )

    np.savez(
        year_dir / f"gim{year}{doy:03d}.npz",
        gim=gim,
        gim_time=gim_time,
    )


def test_temporal_workflow_end_to_end(tmp_path):
    dataset_prefix = tmp_path / "gim"

    start_time = datetime(2022, 5, 28, 6)
    end_time = datetime(2022, 5, 29, 5)
    reference_days = 3

    raw_latitude_index = 20
    longitude_index = 50
    oriented_latitude_index = 70 - raw_latitude_index

    injections = {
        datetime(2022, 5, 28, 7): 42.0,
        datetime(2022, 5, 28, 18): 2.0,
    }

    reference_start = start_time - timedelta(
        days=reference_days
    )

    current_day = reference_start.date()

    while current_day <= end_time.date():
        day = datetime.combine(
            current_day,
            datetime.min.time(),
        )

        write_gim_day(
            dataset_prefix,
            day,
            raw_latitude_index=raw_latitude_index,
            longitude_index=longitude_index,
            injections=injections,
        )

        current_day += timedelta(days=1)

    output_path = tmp_path / "outputs" / "temporal_anomaly.png"

    result = run_temporal_workflow(
        dataset_dir=dataset_prefix,
        start_time=start_time,
        end_time=end_time,
        latitude=float(
            GIM_LATITUDES[oriented_latitude_index]
        ),
        longitude=float(
            GIM_LONGITUDES[longitude_index]
        ),
        output_path=output_path,
        reference_days=reference_days,
        threshold_multiplier=3.0,
        min_reference_samples=3,
        title="Synthetic GIM Temporal Analysis",
    )

    # Validate selected geographic grid.
    assert result.time_series.latitude_index == 50
    assert result.time_series.longitude_index == 50

    # Reference + analysis = 72 + 24 hours.
    assert len(result.time_series.epochs) == 96
    assert len(result.time_series.tec) == 96

    assert result.time_series.epochs[0] == reference_start
    assert result.time_series.epochs[-1] == end_time

    # Framework A returns only the 24 analysis epochs.
    anomaly = result.anomaly_result

    assert len(anomaly.epochs) == 24
    assert anomaly.epochs[0] == start_time
    assert anomaly.epochs[-1] == end_time

    expected = np.zeros(24, dtype=int)
    expected[1] = 1
    expected[12] = -1

    np.testing.assert_array_equal(
        anomaly.anomaly,
        expected,
    )

    np.testing.assert_allclose(
        anomaly.median,
        np.full(24, 10.0),
    )

    np.testing.assert_allclose(
        anomaly.upper_bound,
        np.full(24, 10.0),
    )

    np.testing.assert_allclose(
        anomaly.lower_bound,
        np.full(24, 10.0),
    )

    # Verify the actual PNG artifact.
    assert result.plot_path == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0
    assert output_path.read_bytes()[:8] == (
        b"\x89PNG\r\n\x1a\n"
    )

    # Plotting adapter must close its figure.
    assert plt.get_fignums() == []
