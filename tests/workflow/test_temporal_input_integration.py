"""Synthetic GIM integration test for Framework A input."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.workflow.temporal_input_adapter import (
    load_temporal_tec_from_gim,
)


def write_synthetic_gim_day(
    dataset_prefix: Path,
    day: datetime,
    *,
    raw_latitude_index: int,
    longitude_index: int,
    injected_time: datetime,
):
    year = day.year
    doy = day.timetuple().tm_yday

    year_dir = Path(f"{dataset_prefix}{year}")
    year_dir.mkdir(parents=True, exist_ok=True)

    # GIM values are stored at 10x TECu.
    grid = np.full(
        (24, 71, 73),
        100.0,
        dtype=float,
    )

    if injected_time.date() == day.date():
        hour = injected_time.hour
        grid[hour, raw_latitude_index, longitude_index] = 420.0

    gim = grid.reshape(24 * 71, 73)

    timestamps = np.array(
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

    file_path = year_dir / f"gim{year}{doy:03d}.npz"

    np.savez(
        file_path,
        gim=gim,
        gim_time=timestamps,
    )


def test_synthetic_gim_to_temporal_series(tmp_path):
    dataset_prefix = tmp_path / "gim"

    start_time = datetime(2022, 5, 28, 6)
    end_time = datetime(2022, 5, 28, 8)
    reference_days = 1

    injected_time = datetime(2022, 5, 28, 7)

    raw_latitude_index = 20
    longitude_index = 50

    reference_start = start_time - timedelta(days=reference_days)

    current_day = reference_start.date()

    while current_day <= end_time.date():
        write_synthetic_gim_day(
            dataset_prefix,
            datetime.combine(
                current_day,
                datetime.min.time(),
            ),
            raw_latitude_index=raw_latitude_index,
            longitude_index=longitude_index,
            injected_time=injected_time,
        )

        current_day += timedelta(days=1)

    oriented_latitude_index = 70 - raw_latitude_index

    result = load_temporal_tec_from_gim(
        dataset_dir=dataset_prefix,
        start_time=start_time,
        end_time=end_time,
        latitude=float(
            GIM_LATITUDES[oriented_latitude_index]
        ),
        longitude=float(
            GIM_LONGITUDES[longitude_index]
        ),
        reference_days=reference_days,
    )

    assert len(result.epochs) == 27
    assert result.latitude_index == oriented_latitude_index
    assert result.longitude_index == longitude_index

    assert result.grid_latitude == float(
        GIM_LATITUDES[oriented_latitude_index]
    )

    assert result.grid_longitude == float(
        GIM_LONGITUDES[longitude_index]
    )

    expected_tec = np.full(27, 10.0)

    # Reference period: 24 hours.
    # Injected anomaly: second target hour.
    expected_tec[24 + 1] = 42.0

    np.testing.assert_array_equal(
        result.tec,
        expected_tec,
    )

    assert result.epochs[0] == reference_start
    assert result.epochs[-1] == end_time
