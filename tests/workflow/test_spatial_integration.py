"""End-to-end integration tests for explicit spatial verification."""

from datetime import datetime, timedelta

import numpy as np

from src.workflow.explicit_window import select_explicit_window
from src.workflow.spatial_adapter import run_spatial_verification


def write_synthetic_gim_day(
    dataset_dir,
    day,
    *,
    anomaly_hour=None,
):
    """Write a synthetic daily GIM file in the validated loader format."""

    year_dir = dataset_dir.parent / f"{dataset_dir.name}{day.year}"
    year_dir.mkdir(parents=True, exist_ok=True)

    doy = day.timetuple().tm_yday
    file_path = year_dir / f"gim{day.year}{doy:03d}.npz"

    # 24 hourly maps, 71 x 73 grid points.
    # Stored GIM values are scaled by 10.
    gim = np.full((24 * 71, 73), 100.0, dtype=np.float64)

    if anomaly_hour is not None:
        # One strong positive anomaly at raw grid index (35, 36).
        row = anomaly_hour * 71 + 35
        gim[row, 36] = 500.0

    gim_time = np.array(
        [
            [
                (day + timedelta(hours=hour)).year,
                (day + timedelta(hours=hour)).month,
                (day + timedelta(hours=hour)).day,
                (day + timedelta(hours=hour)).hour,
                0,
                0,
            ]
            for hour in range(24)
        ],
        dtype=np.int64,
    )

    np.savez(
        file_path,
        gim=gim,
        gim_time=gim_time,
    )


def test_explicit_window_spatial_integration(tmp_path):
    """Verify the full workflow with actual loader and computation."""

    dataset_dir = tmp_path / "gim"

    target_start = datetime(2022, 5, 28, 0)
    target_end = datetime(2022, 5, 28, 2)

    reference_days = 3

    reference_start = target_start - timedelta(
        days=reference_days
    )

    # Generate all required daily files.
    current_day = reference_start

    while current_day.date() <= target_end.date():
        anomaly_hour = None

        if current_day.date() == target_start.date():
            anomaly_hour = 1

        write_synthetic_gim_day(
            dataset_dir,
            current_day,
            anomaly_hour=anomaly_hour,
        )

        current_day += timedelta(days=1)

    window = select_explicit_window(
        "2022-05-28T00:00:00Z",
        "2022-05-28T02:00:00Z",
    )

    result = run_spatial_verification(
        window=window,
        dataset_dir=dataset_dir,
        reference_days=reference_days,
        k=3.0,
    )

    assert result.window_steps == 3

    assert result.positive_counts.shape == (71, 73)
    assert result.negative_counts.shape == (71, 73)

    # The injected positive anomaly occurs once in three target hours.
    assert result.positive_counts[35, 36] == 1
    assert np.isclose(
        result.positive_ratio[35, 36],
        100.0 / 3.0,
        rtol=1e-12,
        atol=1e-12,
    )

    # No negative anomaly was injected.
    assert np.count_nonzero(result.negative_counts) == 0

    # No other positive anomaly should appear.
    assert np.count_nonzero(result.positive_counts) == 1

    assert np.sum(result.positive_counts) == 1


def test_cross_year_non_midnight_spatial_integration(tmp_path):
    """Verify spatial workflow across year boundary and non-midnight start."""

    dataset_dir = tmp_path / "gim"

    target_start = datetime(2022, 12, 31, 22)
    target_end = datetime(2023, 1, 1, 2)

    reference_days = 3
    reference_start = target_start - timedelta(
        days=reference_days
    )

    # Generate daily GIM files spanning the year boundary.
    current_day = datetime(
        reference_start.year,
        reference_start.month,
        reference_start.day,
    )

    last_day = datetime(
        target_end.year,
        target_end.month,
        target_end.day,
    )

    while current_day <= last_day:
        anomaly_hour = None

        # Inject one positive anomaly on the new year's first hour.
        if current_day.date() == target_end.date():
            anomaly_hour = 1

        write_synthetic_gim_day(
            dataset_dir,
            current_day,
            anomaly_hour=anomaly_hour,
        )

        current_day += timedelta(days=1)

    window = select_explicit_window(
        "2022-12-31T22:00:00Z",
        "2023-01-01T02:00:00Z",
    )

    result = run_spatial_verification(
        window=window,
        dataset_dir=dataset_dir,
        reference_days=reference_days,
        k=3.0,
    )

    # Five inclusive hourly epochs.
    assert result.window_steps == 5

    # Preserve the validated Framework D grid shape.
    assert result.positive_counts.shape == (71, 73)
    assert result.negative_counts.shape == (71, 73)

    # Exactly one positive anomaly at the injected raw-grid cell.
    assert result.positive_counts[35, 36] == 1

    np.testing.assert_allclose(
        result.positive_ratio[35, 36],
        20.0,
        rtol=1e-12,
        atol=1e-12,
    )

    assert np.sum(result.positive_counts) == 1
    assert np.count_nonzero(result.negative_counts) == 0