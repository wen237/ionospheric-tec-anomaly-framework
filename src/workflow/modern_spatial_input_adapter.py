"""Modern GIM input for Framework D; no scientific computation is changed.

Grid rows are in ascending physical latitude, unlike legacy flattened GIM.
Only hours 00..23 from each owning daily file enter this adapter via bridge.
"""
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.data.modern_gim_bridge import load_modern_gim_window
from src.spatial_verification.gim_loader import SpatialTECData
from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult, compute_spatial_anomalies,
)
from src.spatial_verification.spatial_grid import GIM_LATITUDES, GIM_LONGITUDES
from src.workflow.datetime_adapter import window_to_naive_utc
from src.workflow.temporal_window import TemporalWindow


def load_spatial_tec_from_modern_gim(
    file_paths: Sequence[str | Path],
    start_time: datetime,
    end_time: datetime,
    *,
    reference_days: int = 15,
) -> SpatialTECData:
    """Return Framework D's existing input shape, with ascending-latitude rows."""
    data = load_modern_gim_window(
        file_paths, start_time, end_time, reference_days=reference_days
    )
    if not np.array_equal(data.lat, GIM_LATITUDES) or not np.array_equal(data.lon, GIM_LONGITUDES):
        raise ValueError("Modern GIM coordinates do not match Framework D's global grid.")
    expected_total = reference_days * 24 + data.window_steps
    if data.tec.shape != (expected_total, 71, 73):
        raise ValueError("Modern GIM window has an unexpected TEC shape.")
    expected_times = tuple(
        start_time - timedelta(days=reference_days) + timedelta(hours=i)
        for i in range(expected_total)
    )
    if data.timestamps != expected_times:
        raise ValueError("Modern GIM window timestamps are not continuous UTC hours.")
    return SpatialTECData(
        tec=data.tec.reshape(expected_total, 71 * 73).copy(),
        timestamps=data.timestamps,
        samples_per_day=24,
        reference_days=reference_days,
        window_steps=data.window_steps,
    )


def run_spatial_verification_from_modern_gim(
    window: TemporalWindow,
    file_paths: Sequence[str | Path],
    *,
    reference_days: int = 15,
    k: float = 3.0,
) -> SpatialAnomalyResult:
    """Opt-in Modern GIM path; retains original Framework D calculation."""
    if not isinstance(window, TemporalWindow):
        raise TypeError("window must be a TemporalWindow.")
    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError("reference_days must be a positive integer.")
    if isinstance(k, bool) or not isinstance(k, (int, float)) or not np.isfinite(k) or k < 0:
        raise ValueError("k must be finite and non-negative.")
    start_time, end_time = window_to_naive_utc(window)
    spatial = load_spatial_tec_from_modern_gim(
        file_paths, start_time, end_time, reference_days=reference_days
    )
    return compute_spatial_anomalies(
        tec=spatial.tec,
        samples_per_day=spatial.samples_per_day,
        reference_days=spatial.reference_days,
        window_steps=spatial.window_steps,
        k=float(k),
        latitudes=GIM_LATITUDES,
        longitudes=GIM_LONGITUDES,
    )
