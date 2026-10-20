"""Opt-in modern GIM input adapter for Framework A (Temporal).

The bridge selects each day's own 00..23 UTC maps. This module only
extracts a nearest-grid time series; it never rescales or interpolates TEC.
"""
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from src.data.modern_gim_bridge import load_modern_gim_window
from src.temporal_anomaly.tec_timeseries import TECTimeSeries, extract_tec_timeseries


def load_temporal_tec_from_modern_gim(
    file_paths: Sequence[str | Path],
    start_time: datetime,
    end_time: datetime,
    *,
    latitude: float,
    longitude: float,
    reference_days: int = 15,
) -> TECTimeSeries:
    """Return reference + inclusive analysis hours at the nearest GIM cell.

    Inputs are explicit daily modern NPZ paths, not a provider auto-discovery.
    start_time/end_time are naive, hour-aligned UTC datetimes.
    """
    window = load_modern_gim_window(
        file_paths=file_paths,
        start_time=start_time,
        end_time=end_time,
        reference_days=reference_days,
    )
    return extract_tec_timeseries(
        tec=window.tec,
        epochs=window.timestamps,
        latitudes=window.lat,
        longitudes=window.lon,
        latitude=latitude,
        longitude=longitude,
    )
