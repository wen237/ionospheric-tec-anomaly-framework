
"""Load GIM data into Framework A's temporal time-series contract."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.spatial_verification.gim_loader import load_spatial_tec
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.temporal_anomaly.tec_timeseries import (
    TECTimeSeries,
    extract_tec_timeseries,
)


def load_temporal_tec_from_gim(
    dataset_dir: str | Path,
    start_time: datetime,
    end_time: datetime,
    *,
    latitude: float,
    longitude: float,
    reference_days: int = 15,
) -> TECTimeSeries:
    """Load reference + analysis TEC for one geographic location.

    Times are naive UTC, hourly aligned, and inclusive.
    The returned series includes the reference period.
    """

    if not isinstance(dataset_dir, (str, Path)):
        raise TypeError("dataset_dir must be a string or Path.")

    if not isinstance(start_time, datetime):
        raise TypeError("start_time must be a datetime.")

    if not isinstance(end_time, datetime):
        raise TypeError("end_time must be a datetime.")

    if start_time.tzinfo is not None:
        raise ValueError("start_time must be naive UTC.")

    if end_time.tzinfo is not None:
        raise ValueError("end_time must be naive UTC.")

    for name, value in (
        ("start_time", start_time),
        ("end_time", end_time),
    ):
        if any((
            value.minute,
            value.second,
            value.microsecond,
        )):
            raise ValueError(
                f"{name} must align with an hourly epoch."
            )

    if start_time > end_time:
        raise ValueError("start_time must not exceed end_time.")

    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError("reference_days must be a positive integer.")

    # Reuse Framework D's validated GIM file loader.
    spatial_data = load_spatial_tec(
        dataset_dir=str(dataset_dir),
        start_time=start_time,
        end_time=end_time,
        reference_days=reference_days,
    )

    reference_start = start_time - timedelta(days=reference_days)

    expected_steps = (
        int((end_time - reference_start) / timedelta(hours=1)) + 1
    )

    expected_timestamps = tuple(
        reference_start + timedelta(hours=index)
        for index in range(expected_steps)
    )

    if spatial_data.timestamps != expected_timestamps:
        raise ValueError(
            "GIM timestamps do not match the expected continuous "
            "hourly UTC sequence."
        )

    expected_shape = (
        expected_steps,
        len(GIM_LATITUDES) * len(GIM_LONGITUDES),
    )

    if spatial_data.tec.shape != expected_shape:
        raise ValueError(
            "GIM TEC shape does not match the expected grid dimensions."
        )

    # Framework D preserves raw flattened GIM ordering.
    raw_grid = spatial_data.tec.reshape(
        expected_steps,
        len(GIM_LATITUDES),
        len(GIM_LONGITUDES),
    )

    # Correct the legacy latitude orientation exactly once.
    oriented_grid = np.flip(raw_grid, axis=1)

    # Reuse Framework A's nearest-grid selection.
    return extract_tec_timeseries(
        tec=oriented_grid,
        epochs=spatial_data.timestamps,
        latitudes=GIM_LATITUDES,
        longitudes=GIM_LONGITUDES,
        latitude=latitude,
        longitude=longitude,
    )
