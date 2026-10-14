"""Adapter connecting workflow temporal windows to Framework D."""

from pathlib import Path
from datetime import timedelta
import numpy as np

from src.spatial_verification.gim_loader import load_spatial_tec
from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult,
    compute_spatial_anomalies,
)
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)

from .datetime_adapter import window_to_naive_utc
from .temporal_window import TemporalWindow


def run_spatial_verification(
    window: TemporalWindow,
    dataset_dir: str | Path,
    *,
    reference_days: int = 15,
    k: float = 3.0,
) -> SpatialAnomalyResult:
    """Run validated Framework D computation for a workflow window."""

    if not isinstance(window, TemporalWindow):
        raise TypeError("window must be a TemporalWindow.")

    if not isinstance(dataset_dir, (str, Path)):
        raise TypeError("dataset_dir must be a string or Path.")

    if not isinstance(reference_days, int) or reference_days <= 0:
        raise ValueError("reference_days must be a positive integer.")

    if not np.isfinite(k) or k < 0:
        raise ValueError("k must be finite and non-negative.")

    start_time, end_time = window_to_naive_utc(window)

    spatial_data = load_spatial_tec(
        dataset_dir=str(dataset_dir),
        start_time=start_time,
        end_time=end_time,
        reference_days=reference_days,
    )

    expected_window_steps = int(
        (end_time - start_time).total_seconds() // 3600
    ) + 1

    if spatial_data.window_steps != expected_window_steps:
        raise ValueError(
            "Loaded spatial window does not match the requested "
            "inclusive UTC time range."
        )

    expected_total_steps = (
        reference_days * spatial_data.samples_per_day
        + expected_window_steps
    )

    if spatial_data.tec.shape[0] != expected_total_steps:
        raise ValueError(
            "Loaded TEC data do not contain the expected "
            "reference and target samples."
        )

    expected_reference_start = start_time - timedelta(
        days=reference_days
    )

    expected_timestamps = tuple(
        expected_reference_start + timedelta(hours=i)
        for i in range(expected_total_steps)
    )

    if spatial_data.timestamps != expected_timestamps:
        raise ValueError(
            "Loaded spatial timestamps do not match the "
            "expected continuous hourly UTC sequence."
        )

    return compute_spatial_anomalies(
        tec=spatial_data.tec,
        samples_per_day=spatial_data.samples_per_day,
        reference_days=spatial_data.reference_days,
        window_steps=spatial_data.window_steps,
        k=k,
        latitudes=GIM_LATITUDES,
        longitudes=GIM_LONGITUDES,
    )